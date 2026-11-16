"""Narrow, bounded Nodit statistics transport; never expose provider errors."""

import json
import math
import os
import re
import time
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from .dex_spec import safe_path
from .transport import DatasetBlocked, NoRedirect

METHODS = {
    "active_accounts": "getDailyActiveAccountsStats",
    "transactions": "getDailyTransactionsStats",
}
MAX_BYTES = 1048576


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("NODIT_INVALID_JSON")
        result[key] = value
    return result


def decode_json(body):
    try:
        value = json.loads(body, object_pairs_hook=_pairs)
        json.dumps(value, allow_nan=False)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("NODIT_INVALID_JSON") from None


class NoditTransport:
    def __init__(self, credential_file: Path, *, opener=None):
        try:
            path = safe_path(Path(credential_file))
            if not path.is_file() or path.stat().st_size > 65536:
                raise ValueError
            if os.name != "nt" and path.stat().st_mode & 0o077:
                raise ValueError
            values = re.findall(
                r"(?m)^[ \t]*(?:export[ \t]+)?NODIT_API_KEY[ \t]*=([^\r\n]*)",
                path.read_text(encoding="utf-8-sig"),
            )
            if len(values) != 1:
                raise ValueError
            key = values[0].strip()
            if len(key) >= 2 and key[0] in "\"'" and key[-1] == key[0]:
                key = key[1:-1]
            if not re.fullmatch(r"[A-Za-z0-9._~+/=\-]{12,4096}", key):
                raise ValueError
        except (OSError, ValueError, UnicodeError):
            raise ValueError("NODIT_CREDENTIAL_INVALID") from None
        self._key = key
        self._opener = opener or build_opener(NoRedirect()).open

    def fetch(self, metric, start, end, *, timeout, max_bytes):
        if metric not in METHODS:
            raise ValueError("NODIT_METRIC_NOT_ALLOWED")
        if (
            type(max_bytes) is not int
            or not 0 < max_bytes <= MAX_BYTES
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= 30
        ):
            raise ValueError("NODIT_TRANSPORT_BUDGET_INVALID")
        request = Request(
            "https://web3.nodit.io/v1/ethereum/mainnet/stats/" + METHODS[metric],
            data=json.dumps({"startDate": start, "endDate": end}).encode(),
            headers={
                "X-API-KEY": self._key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
            method="POST",
        )
        try:
            deadline = time.monotonic() + timeout
            with self._opener(request, timeout=timeout) as response:
                if response.status != 200:
                    raise DatasetBlocked("NODIT_RESPONSE_STATUS")
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise DatasetBlocked("NODIT_RESPONSE_ENCODING")
                if (
                    "application/json"
                    not in response.headers.get("Content-Type", "").lower()
                ):
                    raise DatasetBlocked("NODIT_RESPONSE_CONTENT_TYPE")
                body = bytearray()
                read = getattr(response, "read1", response.read)
                # CPython 3.12 urllib responses expose the receiving socket here.
                # Updating it avoids granting a fresh full timeout to each read.
                try:
                    receiving_socket = response.fp.raw._sock
                except AttributeError:
                    raise DatasetBlocked("NODIT_TIMEOUT_CONTROL_UNAVAILABLE") from None
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise DatasetBlocked("NODIT_RESPONSE_TIMEOUT")
                    receiving_socket.settimeout(remaining)
                    chunk = read(min(65536, max_bytes + 1 - len(body)))
                    if time.monotonic() >= deadline:
                        raise DatasetBlocked("NODIT_RESPONSE_TIMEOUT")
                    if not chunk:
                        break
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise DatasetBlocked("NODIT_RESPONSE_TOO_LARGE")
                    # HTTPResponse may close its socket as soon as Content-Length
                    # bytes are consumed. Do not set a timeout on that closed fd.
                    if getattr(response, "isclosed", lambda: False)():
                        break
                body = bytes(body)
            if self._key.encode() in body:
                raise DatasetBlocked("NODIT_SECRET_ECHO")
            value = decode_json(body)
            if self._key in json.dumps(value, ensure_ascii=False):
                raise DatasetBlocked("NODIT_SECRET_ECHO")
            return body
        except HTTPError as error:
            code = error.code
            error.close()
            raise DatasetBlocked(f"NODIT_HTTP_{code}") from None
        except (URLError, OSError, TimeoutError, HTTPException):
            raise DatasetBlocked("NODIT_NETWORK_ERROR") from None
