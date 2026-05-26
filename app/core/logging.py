import logging
from collections.abc import Mapping
from typing import Any


SENSITIVE_KEYS = {
    "authorization",
    "x-access-token",
    "x-app-key",
    "x-signature",
    "app_key",
    "app_secret",
    "access_token",
    "token",
    "signature",
}


def redact_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                safe[key] = "***REDACTED***"
            else:
                safe[key] = redact_payload(item)
        return safe
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # The Webull SDK logs signed request headers before raising errors. Keep provider-level
    # redacted diagnostics, but suppress SDK request dumps so keys/signatures never hit logs.
    logging.getLogger("webull.core.client").setLevel(logging.CRITICAL)
