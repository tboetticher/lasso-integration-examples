import threading
import boto3
from boto3.session import Session
import json
from typing import Any, Dict
import logging
from lasso.hooks.hooks import attach_block_reason

logger = logging.getLogger(__name__)


def _enhance_422_error_message(http_response, parsed: Dict[str, Any], **_: Any) -> None:
    """
    Enhance 422 error messages with block reason from Lasso.

    Runs after attach_block_reason to modify the Error message in the parsed response
    so that when botocore raises ClientError, it includes the block reason.

    The block reason is extracted by attach_block_reason from the response body:
    {"error": {"message": "block reason text"}}
    """
    status = getattr(http_response, "status_code", None)
    if status != 422:
        return

    # Get block reason that was extracted by attach_block_reason hook
    block_reason = parsed.get("BlockReason")
    if not block_reason:
        # No block reason available, leave error message as-is
        return

    # Modify the Error message in the parsed response
    # Botocore will use this when constructing the ClientError exception
    error = parsed.get("Error")
    if error is None:
        # Create Error dict if it doesn't exist
        parsed["Error"] = {
            "Code": "422",
            "Message": f"Request blocked by organization policy. Msg contains {block_reason}",
        }
    else:
        # Update existing Error message
        parsed["Error"] = {
            **error,
            "Code": error.get("Code", "422"),
            "Message": f"Request blocked by organization policy. Msg contains {block_reason}",
        }

_TRACE_HEADERS = (
    "x-request-id",
    "x-tenant-id",
    "x-amzn-requestid",
    "x-amz-request-id",
)

_lock = threading.Lock()
_is_patched = False

_original_boto3_client = boto3.client
_original_session_client = Session.client


def init_patch() -> None:
    """
    Patch boto3 so that:

      * boto3.client(..., proxy_endpoint=..., lasso_api_key=...)
      * Session().client(..., proxy_endpoint=..., lasso_api_key=...)

    are allowed.

    If lasso_api_key is set and the service is 'bedrock-runtime',
    the client adds a 'lasso-x-api-key' header on every request.

    Must be called before creating any clients that should be patched.
    """
    global _is_patched
    with _lock:
        if _is_patched:
            return

        def _make_instrumented_client(original_call, service_name, *args, **kwargs):
            # Pull out our custom kwargs so boto3 does not error.
            lasso_api_key = kwargs.pop("lasso_api_key", None)

            # If proxy_endpoint is set and endpoint_url is not,
            # map it to endpoint_url for this client.
            client = original_call(service_name, *args, **kwargs)

            # Only attach header logic for Bedrock Runtime and when key is set.
            if service_name == "bedrock-runtime" and lasso_api_key:
                def _add_lasso_header(request, **_):
                    # Runs before signing the request.
                    request.headers["lasso-x-api-key"] = lasso_api_key

                # Attach once per client. Wildcard to cover all operations.
                client.meta.events.register(
                    "before-sign.bedrock-runtime.*",
                    _add_lasso_header,
                )

                client.meta.events.register(
                    "after-call.bedrock-runtime.*",
                    attach_block_reason,
                )
                # Enhance 422 error messages with block reason
                # Must run after attach_block_reason to have access to BlockReason
                client.meta.events.register(
                    "after-call.bedrock-runtime.*",
                    _enhance_422_error_message,
                )
            return client

        def patched_boto3_client(service_name, *args, **kwargs):
            return _make_instrumented_client(
                _original_boto3_client,
                service_name,
                *args,
                **kwargs,
            )

        def patched_session_client(self, service_name, *args, **kwargs):
            return _make_instrumented_client(
                lambda svc, *a, **k: _original_session_client(self, svc, *a, **k),
                service_name,
                *args,
                **kwargs,
            )

        # Apply monkey patches.
        boto3.client = patched_boto3_client
        Session.client = patched_session_client

        _is_patched = True
