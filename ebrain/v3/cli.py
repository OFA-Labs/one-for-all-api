"""Additive schema-3 CLI (local opt-in only; legacy `python -m ebrain` unchanged).

Run: `python -m ebrain.v3.cli --enable-v3-local ...`. Without the explicit flag
every mutating/query command exits with an explicit incompatibility error; no
legacy client is silently upgraded and no schema is inferred from a field.
"""
from __future__ import annotations

import argparse
import json
import sys

from .auth.context import DevelopmentPrincipalProvider, build_context
from .clients.adapters import CliAdapter
from .clients.negotiation import check_answer_compatibility, negotiate
from .config import V3Config
from .contracts import Action, Grant, Principal, SchemaVersion, Selector, WriteRequest
from .errors import UnsupportedSchema, V3Error
from .service import V3Service


def _provider(scope: str) -> DevelopmentPrincipalProvider:
    principal = Principal(
        subject="local-dev", org_id="org-demo",
        grants=(Grant(scope=scope, predicates=("*",), actions=tuple(Action),
                      authority="human"),),
        auth_epoch=1,
    )
    return DevelopmentPrincipalProvider(registry={"local-dev": principal})


def _context(service: V3Service, scope: str, schema: str, request_id: str):
    version = negotiate(schema)
    if version is not SchemaVersion.V3:
        raise UnsupportedSchema("this CLI requires schema 3 for V3 commands")
    principal = _provider(scope).authenticate("local-dev")
    return build_context(principal, request_id=request_id, scope=scope), version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m ebrain.v3.cli")
    parser.add_argument("--enable-v3-local", action="store_true",
                        help="explicit opt-in for isolated local schema-3 use")
    parser.add_argument("--persistent", action="store_true",
                        help="use the authoritative PostgreSQL ledger via EBRAIN_V3_TEST_PG_DSN")
    parser.add_argument("--schema", default="3")
    parser.add_argument("--scope", default="one-for-all")
    parser.add_argument("--request-id", default="cli")
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack")
    pack.add_argument("--text", default="")
    pack.add_argument("--resource-id", default="")
    pack.add_argument("--predicate", default="")
    remember = commands.add_parser("remember")
    remember.add_argument("--op-id", required=True)
    remember.add_argument("--resource-id", required=True)
    remember.add_argument("--predicate", default="decision.status")
    remember.add_argument("--repo", default="one-for-all-api")
    remember.add_argument("--environment", default="dev")
    remember.add_argument("--value", required=True)
    commands.add_parser("limits")
    args = parser.parse_args(argv)

    if not args.enable_v3_local:
        print(json.dumps({"error": {"code": "incompatible_client",
                                    "message": "V3 CLI is disabled; use legacy command or opt in locally"},
                          "delivered": "unavailable"}))
        return 3

    if args.persistent:
        import os
        from .db.postgres import DSN_ENV_VAR, PostgresLedger
        dsn = os.environ.get(DSN_ENV_VAR)
        if not dsn:
            print(json.dumps({"error": {"code": "unavailable",
                                        "message": "persistent ledger DSN not configured"}}))
            return 4
        service = V3Service.build(ledger=PostgresLedger(dsn=dsn))
    else:
        service = V3Service.build()
    try:
        ctx, _ = _context(service, args.scope, args.schema, args.request_id)
        if args.command == "pack":
            selector = Selector(
                scope=args.scope, text=args.text,
                resource_id=args.resource_id, predicate=args.predicate,
            )
            delivery = CliAdapter(service).pack(ctx, selector, args.schema)
            result = {"answer_status": delivery.answer.answer_status.value,
                      "items": [i.model_dump(mode="json") for i in delivery.answer.items],
                      "degradation": list(delivery.answer.degradation),
                      "delivered_bytes": delivery.delivered_bytes}
        elif args.command == "remember":
            from ebrain.v3.contracts import ClaimKind, SourceContract
            from ebrain.v3.identity.keys import canonical_key
            key = canonical_key(
                org_id="org-demo", scope=args.scope, resource_namespace="repo",
                resource_id=args.resource_id, predicate=args.predicate,
                kind=ClaimKind.ASSERTION,
                qualifiers={"repo": args.repo, "environment": args.environment},
            )
            receipt = service.write(ctx, WriteRequest(
                op_id=args.op_id, key=key, value=args.value, source_id="cli-local",
                source_revision="1", idempotency_key=args.op_id,
                source_contract=SourceContract.FIRST_PARTY_DECLARED,
            ))
            result = receipt.model_dump(mode="json")
        else:
            result = service.limits(ctx).model_dump(mode="json")
    except V3Error as exc:
        print(json.dumps({"error": exc.body().to_dict()}))
        return 4
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
