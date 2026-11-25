-- E-Brain V3 foundation schema (M8 CP8.1). Isolated, disabled by default.
-- PostgreSQL 16+. Apply with migration role; API/worker roles are non-owner,
-- non-superuser, NOBYPASSRLS. Never point this at legacy/application data.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Roles are created by the test/ops harness with NOLOGIN group memberships.
-- This migration only codifies policies against the current_user setting.

CREATE TABLE IF NOT EXISTS v3_org_state (
    org_id          text PRIMARY KEY,
    knowledge_seq   bigint NOT NULL DEFAULT 0,
    policy_version  text NOT NULL DEFAULT '1',
    identity_generation integer NOT NULL DEFAULT 1,
    auth_epoch      bigint NOT NULL DEFAULT 0,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS v3_principal (
    org_id       text NOT NULL,
    subject      text NOT NULL,
    auth_epoch   bigint NOT NULL DEFAULT 0,
    credential_id text NOT NULL DEFAULT '',
    active       boolean NOT NULL DEFAULT true,
    PRIMARY KEY (org_id, subject)
);

CREATE TABLE IF NOT EXISTS v3_grant (
    grant_id     text PRIMARY KEY,
    org_id       text NOT NULL,
    subject      text NOT NULL,
    scope        text NOT NULL,
    predicates   text[] NOT NULL DEFAULT '{}',
    actions      text[] NOT NULL DEFAULT '{}',
    authority    text NOT NULL CHECK (authority IN ('human','verified','agent')),
    expires_at   timestamptz,
    can_delegate boolean NOT NULL DEFAULT false,
    FOREIGN KEY (org_id, subject) REFERENCES v3_principal(org_id, subject)
);

CREATE TABLE IF NOT EXISTS v3_source_revision (
    org_id        text NOT NULL,
    source_id     text NOT NULL,
    revision      text NOT NULL,
    digest        text NOT NULL,
    parser_version text NOT NULL,
    contract      text NOT NULL CHECK (contract IN
        ('first_party_declared','approved_artifact','external_observation','derived')),
    spans         jsonb NOT NULL DEFAULT '[]'::jsonb,
    acl_lineage   text[] NOT NULL DEFAULT '{}',
    retracted     boolean NOT NULL DEFAULT false,
    partial_scan  boolean NOT NULL DEFAULT false,
    PRIMARY KEY (org_id, source_id, revision)
);

CREATE TABLE IF NOT EXISTS v3_event (
    org_id        text NOT NULL,
    seq           bigint NOT NULL,
    event_id      text NOT NULL,
    scope         text NOT NULL,
    op_id         text NOT NULL,
    payload_digest text NOT NULL,
    event_type    text NOT NULL,
    recorded_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, seq),
    UNIQUE (org_id, scope, op_id, payload_digest)
);

CREATE TABLE IF NOT EXISTS v3_receipt (
    org_id        text NOT NULL,
    idem_key      text NOT NULL,
    idem_key_raw  text NOT NULL,
    op_id         text NOT NULL,
    status        text NOT NULL CHECK (status IN
        ('applied','accepted_pending','accepted_noncurrent','conflict','rejected')),
    knowledge_seq bigint NOT NULL,
    request_digest text NOT NULL,
    scope         text NOT NULL,
    auth_epoch    bigint NOT NULL,
    reason        text NOT NULL DEFAULT '',
    fact_id       text,
    claim_id      text,
    PRIMARY KEY (org_id, idem_key),
    UNIQUE (org_id, scope, idem_key_raw)
);

CREATE TABLE IF NOT EXISTS v3_claim (
    org_id        text NOT NULL,
    claim_id      text PRIMARY KEY,
    seq           bigint NOT NULL,
    scope         text NOT NULL,
    fact_key      text NOT NULL,
    org_scope_key text NOT NULL,
    kind          text NOT NULL CHECK (kind IN
        ('assertion','observation','decision','derived','external','control')),
    value_json    jsonb,
    value_type    text NOT NULL DEFAULT 'scalar',
    unit          text,
    source_id     text NOT NULL,
    source_revision text NOT NULL,
    principal_id  text NOT NULL,
    authority     text NOT NULL DEFAULT 'agent' CHECK (authority IN ('human','verified','agent')),
    delegated_by  text NOT NULL DEFAULT '',
    policy_version text NOT NULL,
    valid_from    timestamptz,
    valid_to      timestamptz,
    recorded_at   timestamptz NOT NULL,
    base_seq      bigint NOT NULL DEFAULT 0,
    observed_seq  bigint NOT NULL DEFAULT 0,
    digest        text NOT NULL,
    fact_id       text,
    suppressed    boolean NOT NULL DEFAULT false,
    FOREIGN KEY (org_id, seq) REFERENCES v3_event(org_id, seq),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from)
);
CREATE INDEX IF NOT EXISTS v3_claim_key_seq ON v3_claim(org_id, scope, fact_key, seq);
CREATE INDEX IF NOT EXISTS v3_claim_fact ON v3_claim(org_id, fact_id);

CREATE TABLE IF NOT EXISTS v3_identity_event (
    org_id        text NOT NULL,
    seq           bigint NOT NULL,
    event_id      text PRIMARY KEY,
    scope         text NOT NULL,
    fact_key      text NOT NULL,
    kind          text NOT NULL CHECK (kind IN
        ('register','bind','unbind_correction','alias','retire_alias','merge','split','rekey')),
    fact_id       text,
    claim_id      text,
    actor         text NOT NULL,
    approval_id   text,
    evidence_digest text NOT NULL DEFAULT '',
    generation    integer NOT NULL DEFAULT 1,
    prior_event_id text,
    reason        text NOT NULL DEFAULT '',
    FOREIGN KEY (org_id, seq) REFERENCES v3_event(org_id, seq)
);

CREATE TABLE IF NOT EXISTS v3_decision (
    org_id        text NOT NULL,
    decision_id   text PRIMARY KEY,
    scope         text NOT NULL,
    kind          text NOT NULL,
    state         text NOT NULL CHECK (state IN
        ('draft','submitted','under_review','approved','rejected','expired','stale','applied','failed')),
    version       integer NOT NULL,
    digest        text NOT NULL,
    targets       text[] NOT NULL DEFAULT '{}',
    evidence      text[] NOT NULL DEFAULT '{}',
    preconditions text[] NOT NULL DEFAULT '{}',
    proposer      text NOT NULL,
    reviewer      text,
    reason        text NOT NULL DEFAULT '',
    expires_at    timestamptz,
    applied_seq   bigint,
    impact_digest text NOT NULL DEFAULT '',
    UNIQUE (org_id, decision_id)
);

CREATE TABLE IF NOT EXISTS v3_vote (
    org_id        text NOT NULL,
    decision_id   text NOT NULL,
    voter         text NOT NULL,
    version       integer NOT NULL,
    approve       boolean NOT NULL,
    digest        text NOT NULL,
    reason        text NOT NULL DEFAULT '',
    PRIMARY KEY (org_id, decision_id, voter),
    FOREIGN KEY (org_id, decision_id) REFERENCES v3_decision(org_id, decision_id)
);

CREATE TABLE IF NOT EXISTS v3_outbox (
    org_id        text NOT NULL,
    job_id        text PRIMARY KEY,
    job_type      text NOT NULL,
    scope         text NOT NULL,
    payload_digest text NOT NULL,
    seq           bigint NOT NULL,
    attempts      integer NOT NULL DEFAULT 0,
    lease_owner   text NOT NULL DEFAULT '',
    lease_expires_seq bigint NOT NULL DEFAULT 0,
    state         text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','leased','applied','dead')),
    last_error    text NOT NULL DEFAULT '',
    applied_at    timestamptz,
    FOREIGN KEY (org_id, seq) REFERENCES v3_event(org_id, seq)
);
CREATE INDEX IF NOT EXISTS v3_outbox_ready ON v3_outbox(org_id, state, seq);

CREATE TABLE IF NOT EXISTS v3_pending_impact (
    org_id        text NOT NULL,
    impact_id     text PRIMARY KEY,
    scope         text NOT NULL,
    fact_key      text,
    domain        text NOT NULL DEFAULT '',
    reason        text NOT NULL,
    created_seq   bigint NOT NULL,
    resolved_seq  bigint,
    claim_id      text NOT NULL DEFAULT '',
    FOREIGN KEY (org_id, created_seq) REFERENCES v3_event(org_id, seq)
);

CREATE TABLE IF NOT EXISTS v3_usage (
    org_id        text NOT NULL,
    scope         text NOT NULL,
    facts         integer NOT NULL DEFAULT 0,
    events        integer NOT NULL DEFAULT 0,
    bytes         bigint NOT NULL DEFAULT 0,
    jobs          integer NOT NULL DEFAULT 0,
    pending       integer NOT NULL DEFAULT 0,
    plan_revision text NOT NULL DEFAULT '1',
    PRIMARY KEY (org_id, scope)
);

CREATE TABLE IF NOT EXISTS v3_suppression (
    org_id        text NOT NULL,
    fact_id       text NOT NULL,
    seq           bigint NOT NULL,
    reason_code   text NOT NULL,
    PRIMARY KEY (org_id, fact_id, seq)
);

CREATE TABLE IF NOT EXISTS v3_audit (
    org_id        text NOT NULL,
    seq           bigint NOT NULL,
    actor         text NOT NULL,
    action        text NOT NULL,
    digest        text NOT NULL,
    recorded_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS v3_audit_seq ON v3_audit(org_id, seq);

-- Every tenant table carries org_id and FORCE RLS. The runtime role sets
-- transaction-local org_id via set_config('v3.org_id', ..., true); policies
-- compare against that trusted setting, never a request body.
DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT unnest(ARRAY[
        'v3_org_state','v3_principal','v3_grant','v3_source_revision','v3_event',
        'v3_receipt','v3_claim','v3_identity_event','v3_decision','v3_vote','v3_outbox',
        'v3_pending_impact','v3_usage','v3_suppression','v3_audit'
    ]) LOOP
        EXECUTE 'ALTER TABLE ' || quote_ident(t) || ' ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE ' || quote_ident(t) || ' FORCE ROW LEVEL SECURITY';
        EXECUTE 'CREATE POLICY ' || quote_ident('tenant_' || t) || ' ON ' || quote_ident(t) ||
            ' USING (org_id = current_setting(''v3.org_id'', true)) ' ||
            'WITH CHECK (org_id = current_setting(''v3.org_id'', true))';
    END LOOP;
END $$;

-- Watermark/audit helpers are intentionally minimal; no arbitrary SQL is
-- exposed to clients or MCP tools.
COMMIT;

-- Migration checksum is recorded by tools/ebrain/operations/migrate.py.
