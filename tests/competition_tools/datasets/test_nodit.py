import io
import json
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from competition_tools.datasets import nodit
from competition_tools.datasets.nodit_transport import NoditTransport


NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)
KEY = "synthetic-nodit-test-credential"


class Response(io.BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, body):
        super().__init__(body)
        self.fp = SimpleNamespace(
            raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=lambda value: None))
        )


def credential(tmp_path):
    p = tmp_path / "private.env"
    p.write_text("UNRELATED=do-not-execute\nNODIT_API_KEY=" + KEY + "\n")
    p.chmod(0o600)
    return p


def payload(first=12):
    return json.dumps(
        {
            "count": 2,
            "items": [
                {"date": "2026-11-14", "count": first},
                {"date": "2026-11-15", "count": 20},
            ],
        }
    ).encode()


def collect(tmp_path, opener=None, **kwargs):
    transport = NoditTransport(
        credential(tmp_path), opener=opener or (lambda *a, **k: Response(payload()))
    )
    return nodit.collect(
        "2026-11-14",
        "2026-11-15",
        tmp_path / "run",
        transport=transport,
        now=NOW,
        sleep=lambda _: None,
        **kwargs,
    )


def test_collect_normalizes_both_series_and_verifies_without_key(tmp_path):
    result = collect(tmp_path)
    out = tmp_path / "run"
    assert result["status"] == "acquired"
    assert result["attempts"] == 2 and result["estimated_cu"] == 300
    assert (out / "normalized.csv").read_text() == (
        "date,active_accounts,transactions\n2026-11-14,12,12\n2026-11-15,20,20\n"
    )
    (tmp_path / "private.env").unlink()
    assert nodit.verify(out)["status"] == "acquired"
    assert all(KEY not in p.read_text() for p in out.rglob("*") if p.is_file())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_requests": 1},
        {"max_cu": 299},
        {"max_requests": 5},
        {"max_cu": 601},
        {"max_seconds": 121},
    ],
)
def test_budget_preflight_does_not_start_requests_or_create_output(tmp_path, kwargs):
    def forbidden(*args, **kw):
        pytest.fail("network must not be called")

    with pytest.raises(ValueError):
        collect(tmp_path, forbidden, **kwargs)
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize(
    "start,end",
    [
        ("2026-11-16", "2026-11-16"),
        ("2026-01-01", "2026-11-15"),
        ("2026-11-15", "2026-11-14"),
        ("2026-1-01", "2026-01-02"),
    ],
)
def test_invalid_window_rejected_before_requests(tmp_path, start, end):
    with pytest.raises(ValueError):
        nodit.collect(start, end, tmp_path / "run", transport=None, now=NOW)
    assert not (tmp_path / "run").exists()


def test_yesterday_not_eligible_until_utc_publication_delay(tmp_path):
    with pytest.raises(ValueError):
        nodit.collect(
            "2026-11-15",
            "2026-11-15",
            tmp_path / "run",
            transport=None,
            now=datetime(2026, 11, 16, 0, 29, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("code", [401, 403, 429, 503, 302])
def test_http_failure_is_charged_and_never_retried_or_leaked(tmp_path, code):
    def fail(request, **kwargs):
        raise HTTPError(request.full_url, code, KEY, {}, io.BytesIO(KEY.encode()))

    result = collect(tmp_path, fail)
    assert result["attempts"] == 1 and result["estimated_cu"] == 150
    assert (
        result["status"] == "blocked" and result["issue_code"] == f"NODIT_HTTP_{code}"
    )
    assert not (tmp_path / "run/manifest.json").exists()
    assert KEY not in (tmp_path / "run/receipt.json").read_text()


def test_network_failure_retains_uncertain_spend(tmp_path):
    def fail(*args, **kw):
        raise URLError(KEY)

    result = collect(tmp_path, fail)
    assert result["status"] == "blocked" and result["spend_uncertain"]
    assert result["attempts"] == 1


@pytest.mark.parametrize(
    "raw",
    [
        b'{"items":[],"items":[]}',
        b'{"items":NaN}',
        b'{"items":1e999}',
        b"not json",
        b"{}" * 600000,
        json.dumps({"echo": KEY}).encode(),
        ('{"echo":"' + "".join("\\u%04x" % ord(c) for c in KEY) + '"}').encode(),
    ],
)
def test_malformed_or_secret_response_is_not_retained(tmp_path, raw):
    result = collect(tmp_path, lambda *a, **k: Response(raw))
    assert result["status"] == "blocked"
    assert not list((tmp_path / "run/raw").glob("*.json"))
    assert KEY not in (tmp_path / "run/receipt.json").read_text()


@pytest.mark.parametrize(
    "items",
    [
        [{"date": "2026-11-14", "count": 12}],
        [{"date": "2026-11-14", "count": 12}, {"date": "2026-11-14", "count": 20}],
        [{"date": "2026-11-14", "count": -1}, {"date": "2026-11-15", "count": 20}],
        [{"date": "2026-11-14", "count": True}, {"date": "2026-11-15", "count": 20}],
        [{"date": "2026-11-13", "count": 12}, {"date": "2026-11-15", "count": 20}],
    ],
)
def test_incomplete_or_invalid_series_retains_raw_without_success(tmp_path, items):
    raw = json.dumps({"count": len(items), "items": items}).encode()
    result = collect(tmp_path, lambda *a, **k: Response(raw))
    assert result["status"] == "blocked"
    assert (tmp_path / "run/raw/active_accounts.json").read_bytes() == raw
    assert not (tmp_path / "run/normalized.csv").exists()


@pytest.mark.parametrize("mutation", ["csv", "extra", "receipt"])
def test_offline_verify_detects_tampering(tmp_path, mutation):
    collect(tmp_path)
    out = tmp_path / "run"
    name = {
        "csv": "normalized.csv",
        "extra": "unlisted.json",
        "receipt": "receipt.json",
    }[mutation]
    (out / name).write_text("changed")
    with pytest.raises(ValueError):
        nodit.verify(out)


def test_existing_output_is_never_overwritten(tmp_path):
    collect(tmp_path)
    before = (tmp_path / "run/manifest.json").read_bytes()
    with pytest.raises((ValueError, FileExistsError)):
        collect(tmp_path)
    assert (tmp_path / "run/manifest.json").read_bytes() == before


def test_symlink_output_and_source_destination_rejected(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "alias"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError):
        nodit.collect("2026-11-14", "2026-11-15", link / "run", transport=None, now=NOW)
    with pytest.raises(ValueError):
        nodit.collect(
            "2026-11-14",
            "2026-11-15",
            Path.cwd() / "unsafe-run",
            transport=None,
            now=NOW,
        )


@pytest.mark.parametrize(
    "contents",
    [
        "NODIT_API_KEY=\n",
        "NODIT_API_KEY=a\nNODIT_API_KEY=b\n",
        "NODIT_API_KEY=$(unsafe)\n",
        "OTHER_KEY=value\n",
    ],
)
def test_bad_credentials_rejected_without_executing_or_disclosing(tmp_path, contents):
    p = credential(tmp_path)
    p.write_text(contents)
    with pytest.raises(ValueError, match="NODIT_CREDENTIAL"):
        NoditTransport(p)


def test_insecure_credential_permissions_rejected(tmp_path):
    p = credential(tmp_path)
    p.chmod(0o644)
    with pytest.raises(ValueError, match="NODIT_CREDENTIAL"):
        NoditTransport(p)


def test_transport_uses_only_fixed_host_header_authentication(tmp_path):
    def inspect(request, **kwargs):
        assert (
            request.full_url
            == "https://web3.nodit.io/v1/ethereum/mainnet/stats/getDailyActiveAccountsStats"
        )
        assert request.get_header("X-api-key") == KEY
        assert KEY not in request.full_url and KEY.encode() not in request.data
        assert json.loads(request.data) == {
            "startDate": "2026-11-14",
            "endDate": "2026-11-15",
        }
        return Response(payload())

    transport = NoditTransport(credential(tmp_path), opener=inspect)
    assert (
        transport.fetch(
            "active_accounts", "2026-11-14", "2026-11-15", timeout=10, max_bytes=1024
        )
        == payload()
    )
    with pytest.raises(ValueError):
        transport.fetch(
            "https://evil.example",
            "2026-11-14",
            "2026-11-15",
            timeout=10,
            max_bytes=1024,
        )


def test_cli_verify_success_and_missing_bundle_exit_status(tmp_path, capsys):
    collect(tmp_path)
    assert nodit.main(["verify", "--output", str(tmp_path / "run")]) == 0
    assert json.loads(capsys.readouterr().out)["rows"] == 2
    assert nodit.main(["verify", "--output", str(tmp_path / "missing")]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"


def test_second_failure_retains_first_response_and_both_attempts(tmp_path):
    def respond(request, **kwargs):
        if request.full_url.endswith("getDailyTransactionsStats"):
            raise URLError(KEY)
        return Response(payload())

    result = collect(tmp_path, respond)
    assert result["attempts"] == 2 and result["estimated_cu"] == 300
    assert result["status"] == "blocked" and result["spend_uncertain"]
    assert (tmp_path / "run/raw/active_accounts.json").exists()
    assert not (tmp_path / "run/normalized.csv").exists()


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "text/html"},
        {"Content-Type": "application/json", "Content-Encoding": "gzip"},
    ],
)
def test_disallowed_content_type_or_compression_is_not_saved(tmp_path, headers):
    def respond(*args, **kw):
        response = Response(payload())
        response.headers = headers
        return response

    result = collect(tmp_path, respond)
    assert result["status"] == "blocked"
    assert not list((tmp_path / "run/raw").iterdir())


def test_verify_rejects_symlinked_manifest(tmp_path):
    collect(tmp_path)
    manifest = tmp_path / "run/manifest.json"
    saved = tmp_path / "manifest-copy.json"
    manifest.rename(saved)
    manifest.symlink_to(saved)
    with pytest.raises(ValueError):
        nodit.verify(tmp_path / "run")


def test_verify_rejects_csv_change_even_with_updated_hash(tmp_path):
    import hashlib

    collect(tmp_path)
    out = tmp_path / "run"
    csvfile = out / "normalized.csv"
    csvfile.write_text(
        "date,active_accounts,transactions\n2026-11-14,999,12\n2026-11-15,20,20\n"
    )
    manifest = json.loads((out / "manifest.json").read_text())
    for row in manifest["files"]:
        if row["path"] == "normalized.csv":
            row.update(
                bytes=csvfile.stat().st_size,
                sha256=hashlib.sha256(csvfile.read_bytes()).hexdigest(),
            )
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        nodit.verify(out)


@pytest.mark.parametrize(
    "mutation", ["missing_observed", "missing_completed", "naive_observed", "reversed"]
)
def test_verify_requires_ordered_aware_observation_times(tmp_path, mutation):
    import hashlib

    collect(tmp_path)
    out = tmp_path / "run"
    state = json.loads((out / "receipt.json").read_text())
    if mutation == "missing_observed":
        del state["observations"][0]["observed_at"]
    elif mutation == "missing_completed":
        del state["completed_at"]
    elif mutation == "naive_observed":
        state["observations"][0]["observed_at"] = "2026-11-16T12:00:00"
    else:
        state["completed_at"] = "2026-11-01T00:00:00Z"
    file = out / "receipt.json"
    file.write_text(json.dumps(state))
    manifest = json.loads((out / "manifest.json").read_text())
    for row in manifest["files"]:
        if row["path"] == "receipt.json":
            row.update(
                bytes=file.stat().st_size,
                sha256=hashlib.sha256(file.read_bytes()).hexdigest(),
            )
    (out / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        nodit.verify(out)


def test_verify_rejects_extra_dangling_symlink(tmp_path):
    collect(tmp_path)
    (tmp_path / "run/dangling").symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError):
        nodit.verify(tmp_path / "run")


def test_socket_timeout_shrinks_to_remaining_deadline(tmp_path, monkeypatch):
    from competition_tools.datasets import nodit_transport

    clock = [0.0]
    timeouts = []

    class SlowResponse(Response):
        def __init__(self):
            super().__init__(payload())
            self.fp.raw._sock.settimeout = timeouts.append

        def read(self, size):
            body = super().read(size)
            if body:
                clock[0] += 9
            return body

        read1 = read

    monkeypatch.setattr(nodit_transport.time, "monotonic", lambda: clock[0])
    transport = NoditTransport(
        credential(tmp_path), opener=lambda *a, **kw: SlowResponse()
    )
    transport.fetch(
        "active_accounts", "2026-11-14", "2026-11-15", timeout=10, max_bytes=1024
    )
    assert timeouts == [10, 1]


def test_delayed_headers_block_response_when_control_returns(tmp_path, monkeypatch):
    from competition_tools.datasets import nodit_transport

    clock = [0.0]

    def opener(*args, **kwargs):
        clock[0] = 11
        return Response(payload())

    monkeypatch.setattr(nodit_transport.time, "monotonic", lambda: clock[0])
    transport = NoditTransport(credential(tmp_path), opener=opener)
    with pytest.raises(ValueError, match="NODIT_RESPONSE_TIMEOUT"):
        transport.fetch(
            "active_accounts", "2026-11-14", "2026-11-15", timeout=10, max_bytes=1024
        )


def test_real_urllib_response_can_close_socket_after_last_chunk(tmp_path):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread
    from urllib.request import urlopen

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = payload()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:

        def opener(request, *, timeout):
            return urlopen(
                f"http://127.0.0.1:{server.server_port}/",
                data=request.data,
                timeout=timeout,
            )

        transport = NoditTransport(credential(tmp_path), opener=opener)
        assert (
            transport.fetch(
                "active_accounts",
                "2026-11-14",
                "2026-11-15",
                timeout=10,
                max_bytes=1024,
            )
            == payload()
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
