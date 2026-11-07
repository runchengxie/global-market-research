"""Exact credential-free intraday archive URLs in a deadline-bound worker."""

import sys
import urllib.request
import urllib.error
from .binance_intraday import PRODUCTS, MONTHS, archive_url
from .binance_daily_transport import NoRedirect, run_worker


def validate_url(url):
    if url not in {
        archive_url(p, m) + s
        for p in PRODUCTS
        for m in MONTHS
        for s in ("", ".CHECKSUM")
    }:
        raise ValueError("UNAPPROVED_INTRADAY_URL")


class IntradayTransport:
    def fetch(self, url, *, max_bytes, timeout):
        validate_url(url)
        return run_worker(
            [sys.executable, "-m", __name__, url, str(max_bytes), str(timeout)],
            timeout=timeout,
            max_bytes=max_bytes,
        )


def main():
    url, limit, timeout = sys.argv[1:]
    validate_url(url)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(
            urllib.request.Request(
                url, headers={"User-Agent": "global-market-research-archive/1"}
            ),
            timeout=float(timeout),
        )
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        body = response.read(int(limit) + 1)
        code = response.status
    if len(body) > int(limit):
        raise ValueError("RESPONSE_TOO_LARGE")
    sys.stdout.buffer.write(int(code).to_bytes(4, "big") + body)


if __name__ == "__main__":
    main()
