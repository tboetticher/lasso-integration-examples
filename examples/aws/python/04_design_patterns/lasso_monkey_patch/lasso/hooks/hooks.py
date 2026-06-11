import json
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

_TRACE_HEADERS = (
    "x-request-id",
    "x-tenant-id",
    "x-amzn-requestid",
    "x-amz-request-id",
)

def attach_block_reason(http_response, parsed: Dict[str, Any], **_: Any) -> None:
    """
    Attach error details to the parsed response for ClientError handling.

    - 422: parsed["BlockReason"] from {"error":{"message": "..."}}
    - 403: parsed["AccessDeniedReason"] from {"message": "..."} or name/error.message
    - Trace: parsed["LassoTrace"] from known trace headers if present
    """
    try:
        ctype = (http_response.headers.get("Content-Type") or "").lower()
        if "application/json" not in ctype:
            return
        data = json.loads(http_response.text or "{}")
    except Exception as exc:
        logger.debug("attach_block_reason: failed to parse JSON: %s", exc)
        data = {}

    status = getattr(http_response, "status_code", None)

    if status == 422:
        # Lasso policy block format
        reason = (data.get("error") or {}).get("message")
        if isinstance(reason, str) and reason.strip():
            parsed["BlockReason"] = reason.strip()

    elif status == 403:
        # Common forbidden payload: {"message":"Forbidden", "name":"ForbiddenException", ...}
        reason = (
            data.get("message")
            or (data.get("error") or {}).get("message")
            or data.get("name")
        )
        if isinstance(reason, str) and reason.strip():
            parsed["AccessDeniedReason"] = reason.strip()

    # Optional append trace headers to message
    trace = {k: http_response.headers[k] for k in _TRACE_HEADERS if k in http_response.headers}
    if trace:
        parsed["LassoTrace"] = trace