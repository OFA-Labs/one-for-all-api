"""Machine-readable V3 error codes and exceptions.

Error codes are part of the frozen schema-3 contract (see CONTRACTS.md). A client
must be able to branch on ``code`` without parsing ``message``. Security-sensitive
cases use an indistinguishable code; no detail about hidden facts leaks here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ErrorBody:
    code: str
    message: str
    request_id: str
    retryable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "request_id": self.request_id,
            "retryable": self.retryable,
        }


# Stable reason codes. Adding a code is additive; changing one is a schema change.
MALFORMED: Final = "malformed"                     # 400
UNAUTHENTICATED: Final = "unauthenticated"          # 401
FORBIDDEN: Final = "forbidden"                      # 403 (existence is safe)
NOT_FOUND: Final = "not_found"                      # 404 (existence indistinguishable)
IDEMPOTENCY_CONFLICT: Final = "idempotency_conflict"  # 409
STALE_BASE: Final = "stale_base"                    # 409
STALE_REVIEW: Final = "stale_review"                # 409
TOO_LARGE: Final = "too_large"                      # 413
SEMANTIC_REJECT: Final = "semantic_reject"          # 422
UNSUPPORTED_PREDICATE: Final = "unsupported_predicate"  # 422
QUOTA_EXCEEDED: Final = "quota_exceeded"            # 429
RATE_LIMITED: Final = "rate_limited"                # 429
UNAVAILABLE: Final = "unavailable"                  # 503
UNSUPPORTED_SCHEMA: Final = "unsupported_schema"    # 400/406
UNAUTHORIZED_CURRENT: Final = "unauthorized_current"  # denial, no detail
ERASED: Final = "erased"                            # denial, no detail
AMBIGUOUS_IDENTITY: Final = "ambiguous_identity"    # pending/review
PENDING_IMPACT: Final = "pending_impact"            # not current
REJECTED_CONTENT: Final = "rejected_content"        # gate rejection
INCOMPATIBLE_GENERATION: Final = "incompatible_generation"
AUTH_EPOCH_CHANGED: Final = "auth_epoch_changed"

HTTP_STATUS: Final[dict[str, int]] = {
    MALFORMED: 400,
    UNAUTHENTICATED: 401,
    FORBIDDEN: 403,
    NOT_FOUND: 404,
    IDEMPOTENCY_CONFLICT: 409,
    STALE_BASE: 409,
    STALE_REVIEW: 409,
    TOO_LARGE: 413,
    SEMANTIC_REJECT: 422,
    UNSUPPORTED_PREDICATE: 422,
    QUOTA_EXCEEDED: 429,
    RATE_LIMITED: 429,
    UNAVAILABLE: 503,
    UNSUPPORTED_SCHEMA: 400,
    UNAUTHORIZED_CURRENT: 403,
    ERASED: 403,
    AMBIGUOUS_IDENTITY: 409,
    PENDING_IMPACT: 409,
    REJECTED_CONTENT: 422,
    INCOMPATIBLE_GENERATION: 409,
    AUTH_EPOCH_CHANGED: 409,
}


class V3Error(Exception):
    """Base class for all V3 failures. Carries a stable code and request id."""

    code: str = SEMANTIC_REJECT
    retryable: bool = False
    http_status: int = 422

    def __init__(
        self,
        message: str,
        *,
        request_id: str = "unknown",
        code: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        self.message = message
        self.request_id = request_id
        if code is not None:
            self.code = code
        if retryable is not None:
            self.retryable = retryable
        self.http_status = HTTP_STATUS.get(self.code, self.http_status)
        super().__init__(f"[{self.code}] {message}")

    def body(self) -> ErrorBody:
        return ErrorBody(self.code, self.message, self.request_id, self.retryable)


class Malformed(V3Error):
    code, http_status = MALFORMED, 400


class Unauthenticated(V3Error):
    code, http_status = UNAUTHENTICATED, 401


class Forbidden(V3Error):
    code, http_status = FORBIDDEN, 403


class NotFound(V3Error):
    code, http_status = NOT_FOUND, 404


class IdempotencyConflict(V3Error):
    code, http_status = IDEMPOTENCY_CONFLICT, 409


class StaleBase(V3Error):
    code, http_status = STALE_BASE, 409


class StaleReview(V3Error):
    code, http_status = STALE_REVIEW, 409


class TooLarge(V3Error):
    code, http_status = TOO_LARGE, 413


class SemanticReject(V3Error):
    code, http_status = SEMANTIC_REJECT, 422


class UnsupportedPredicate(V3Error):
    code, http_status = UNSUPPORTED_PREDICATE, 422


class QuotaExceeded(V3Error):
    code, http_status = QUOTA_EXCEEDED, 429

    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(message, retryable=True, **kwargs)  # type: ignore[arg-type]


class RateLimited(V3Error):
    code, http_status = RATE_LIMITED, 429

    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(message, retryable=True, **kwargs)  # type: ignore[arg-type]


class Unavailable(V3Error):
    code, http_status = UNAVAILABLE, 503

    def __init__(self, message: str, **kwargs: object) -> None:
        super().__init__(message, retryable=True, **kwargs)  # type: ignore[arg-type]


class UnsupportedSchema(V3Error):
    code, http_status = UNSUPPORTED_SCHEMA, 400


class RejectedContent(V3Error):
    code, http_status = REJECTED_CONTENT, 422


class AmbiguousIdentity(V3Error):
    code, http_status = AMBIGUOUS_IDENTITY, 409


class IncompatibleGeneration(V3Error):
    code, http_status = INCOMPATIBLE_GENERATION, 409


class AuthEpochChanged(V3Error):
    code, http_status = AUTH_EPOCH_CHANGED, 409
    retryable = True
