# utils/errors.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

_TRACE_KEYS = ("x-request-id", "x-amzn-requestid", "x-amz-request-id", "x-tenant-id")

@dataclass(frozen=True)
class BedrockErrorInfo:
    """Normalized details from a botocore ClientError for Bedrock + proxy."""
    status: Optional[int]
    request_id: Optional[str]
    block_reason: Optional[str]
    access_denied_reason: Optional[str]
    trace: Mapping[str, str]
    aws_error_code: Optional[str] = None
    aws_error_message: Optional[str] = None


def _response(err: ClientError) -> Dict[str, Any]:
    """Return the embedded response dict or an empty dict."""
    return getattr(err, "response", {}) or {}


def _pick_request_id(resp: Mapping[str, Any]) -> Optional[str]:
    """Prefer proxy trace IDs, then fall back to AWS RequestId."""
    trace = resp.get("LassoTrace") or {}
    for key in _TRACE_KEYS:
        val = trace.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    meta = resp.get("ResponseMetadata") or {}
    rid = meta.get("RequestId")
    return rid.strip() if isinstance(rid, str) and rid.strip() else None


def extract_bedrock_error_info(err: ClientError) -> BedrockErrorInfo:
    """
    Build BedrockErrorInfo from ClientError.

    Expects the after-call hook to set BlockReason (422), AccessDeniedReason (403),
    and LassoTrace. Still works if those fields are absent.
    """
    resp = _response(err)
    # print ("Lasso", resp)
    meta = resp.get("ResponseMetadata") or {}
    aws_err = resp.get("Error") or {}

    block = resp.get("BlockReason")
    access = resp.get("AccessDeniedReason")

    return BedrockErrorInfo(
        status=meta.get("HTTPStatusCode"),
        request_id=_pick_request_id(resp),
        block_reason=block.strip() if isinstance(block, str) and block.strip() else None,
        access_denied_reason=access.strip() if isinstance(access, str) and access.strip() else None,
        trace=resp.get("LassoTrace") or {},
        aws_error_code=aws_err.get("Code"),
        aws_error_message=aws_err.get("Message"),
    )


def handle_bedrock_client_error(
    err: ClientError,
    *,
    reraise: bool = False,
) -> BedrockErrorInfo:
    """
    Log a single clear line per error class and return normalized info.

    - 422: policy block (uses BlockReason)
    - 403: access denied (uses AccessDeniedReason or 'Forbidden')
    - else: generic failure (logs HTTP status)

    Set reraise=True to re-raise after logging.
    """
    info = extract_bedrock_error_info(err)
    rid = info.request_id or "N/A"

    if info.status == 422 and info.block_reason:
        logger.error(
            "Request blocked by organization policy: %s [request-id=%s]",
            info.block_reason,
            rid,
        )
    elif info.status == 403:
        logger.error(
            "Access denied by proxy: %s [request-id=%s]",
            info.access_denied_reason or "Forbidden",
            rid,
        )
    else:
        logger.error("Bedrock call failed. HTTP %s [request-id=%s]", info.status, rid)

    if reraise:
        raise err
    return info
