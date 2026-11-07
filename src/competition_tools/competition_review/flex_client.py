"""Bounded read-only Flex HTTPS; credentials never enter diagnostics."""

from dataclasses import dataclass, field
from datetime import date
import os
from pathlib import Path
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from competition_tools.crypto_evidence import read_json
from competition_tools.datasets.daily_storage import safe_path

BASE = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"
MAX_BYTES = 16 * 1024 * 1024


class FlexError(ValueError):
    """Stable diagnostic code, never an upstream message or credential URL."""


@dataclass(frozen=True)
class Credentials:
    token: str = field(repr=False)
    query_id: str = field(repr=False)
    expected_account: str = field(repr=False)
    account_ref: str
    base_currency: str


def load_config(path):
    try:
        p = safe_path(Path(path))
        info = p.stat()
        if os.name == "posix" and (
            info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise FlexError("FLEX_CONFIG_NOT_PRIVATE")
        if info.st_size > 8192:
            raise FlexError("FLEX_CONFIG_INVALID")
        r = read_json(p)
        if any(
            not isinstance(r.get(k), str)
            for k in [
                "token",
                "query_id",
                "expected_account",
                "account_ref",
                "base_currency",
            ]
        ):
            raise FlexError("FLEX_CONFIG_INCOMPLETE")
        if not re.fullmatch(r"[0-9]{6,128}", r["token"]) or not re.fullmatch(
            r"[0-9]{1,32}", r["query_id"]
        ):
            raise FlexError("FLEX_CONFIG_INCOMPLETE")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", r["account_ref"]) or (
            r["base_currency"] and not re.fullmatch(r"[A-Z]{3}", r["base_currency"])
        ):
            raise FlexError("FLEX_CONFIG_INVALID")
        if len(r["expected_account"]) > 128 or any(
            ord(c) < 32 for c in r["expected_account"]
        ):
            raise FlexError("FLEX_CONFIG_INVALID")
        return Credentials(
            **{
                k: r[k]
                for k in [
                    "token",
                    "query_id",
                    "expected_account",
                    "account_ref",
                    "base_currency",
                ]
            }
        )
    except FlexError:
        raise
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        raise FlexError("FLEX_CONFIG_INVALID") from None


def parse_xml(raw):
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise FlexError("FLEX_RESPONSE_SIZE")
    if b"\x00" in raw or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise FlexError("FLEX_UNSAFE_XML")
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError):
        raise FlexError("FLEX_XML_REQUIRED") from None
    stack = [(root, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if depth > 32 or count > 200000:
            raise FlexError("FLEX_XML_LIMIT")
        stack.extend((child, depth + 1) for child in item)
    return root


def secret_echo(raw, token, root=None):
    if token.encode() in raw:
        return True
    root = parse_xml(raw) if root is None else root
    return any(
        token in (value or "")
        for element in root.iter()
        for value in [element.text, element.tail, *element.attrib.values()]
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise FlexError("FLEX_REDIRECT_REJECTED")


def http_get(endpoint, params):
    if endpoint not in [BASE + "/SendRequest", BASE + "/GetStatement"] or not set(
        params
    ) <= {"t", "q", "v", "fd", "td"}:
        raise FlexError("FLEX_ENDPOINT_REJECTED")
    request = urllib.request.Request(
        endpoint + "?" + urllib.parse.urlencode(params),
        headers={
            "User-Agent": "global-market-research-flex/1",
            "Accept": "application/xml",
        },
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(
            request, timeout=30
        ) as response:
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise FlexError("FLEX_RESPONSE_SIZE")
        return raw
    except FlexError:
        raise
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        raise FlexError(f"FLEX_HTTP_{code}") from None
    except (OSError, ValueError):
        raise FlexError("FLEX_TRANSPORT_UNAVAILABLE") from None


def _service_code(root):
    code = root.findtext("ErrorCode", "")
    return code if re.fullmatch(r"[0-9]{1,5}", code) else "UNKNOWN"


def fetch_report(
    config, *, start=None, end=None, transport=http_get, sleep=time.sleep, max_polls=6
):
    if type(max_polls) is not int or not 1 <= max_polls <= 12:
        raise FlexError("FLEX_INVALID_POLL_LIMIT")
    params = dict(t=config.token, q=config.query_id, v="3")
    if (start is None) != (end is None):
        raise FlexError("FLEX_DATE_PAIR_REQUIRED")
    if start is not None:
        try:
            a, b = date.fromisoformat(start), date.fromisoformat(end)
        except (ValueError, TypeError):
            raise FlexError("FLEX_INVALID_DATES") from None
        if a > b or (b - a).days >= 365:
            raise FlexError("FLEX_INVALID_DATES")
        params.update(fd=a.strftime("%Y%m%d"), td=b.strftime("%Y%m%d"))
    root = parse_xml(transport(BASE + "/SendRequest", params))
    if root.tag != "FlexStatementResponse" or root.findtext("Status") != "Success":
        raise FlexError("FLEX_SERVICE_" + _service_code(root))
    reference = root.findtext("ReferenceCode", "")
    if not re.fullmatch(r"[0-9]{1,64}", reference):
        raise FlexError("FLEX_INVALID_REFERENCE")
    # Deliberately ignore the response's URL; only the fixed official host is used.
    for _ in range(max_polls):
        sleep(10)
        raw = transport(
            BASE + "/GetStatement", dict(t=config.token, q=reference, v="3")
        )
        root = parse_xml(raw)
        if root.tag == "FlexQueryResponse":
            if secret_echo(raw, config.token, root):
                raise FlexError("FLEX_SECRET_ECHO_REJECTED")
            return raw
        code = _service_code(root)
        if root.tag != "FlexStatementResponse" or code not in {"1009", "1019"}:
            raise FlexError("FLEX_SERVICE_" + code)
    raise FlexError("FLEX_REPORT_NOT_READY")
