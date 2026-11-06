import pytest
from equity_lab.study.sequence.viewer import write_viewer


def test_offline_viewer_escapes_and_contains_accessible_fallback(tmp_path):
    data = dict(
        schema="equity_lab.sequence_diagnostics.v1",
        status="partial",
        reason="INTERRUPTED",
        records=[],
        pending=1,
        provenance={"note": "</script><script>alert(1)</script>"},
    )
    output = tmp_path / "browser.html"
    write_viewer(data, output)
    text = output.read_text()
    assert "</script><script>alert(1)</script>" not in text
    assert "connect-src" in text and "data-report-table" in text
    assert "zh-CN" in text and "partial" in text


def test_unknown_summary_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="PROJECTION"):
        write_viewer({"status": "completed", "records": []}, tmp_path / "bad.html")


def test_embedded_json_roundtrips_script_delimiters(tmp_path):
    import json
    import re

    value = dict(
        schema="equity_lab.sequence_diagnostics.v1",
        status="partial",
        records=[],
        pending=1,
        provenance={"note": "<script>&value</script>"},
    )
    path = tmp_path / "file.html"
    write_viewer(value, path)
    embedded = re.search(
        r'<script type="application/json" data-payload>(.*?)</script>',
        path.read_text(),
        re.S,
    ).group(1)
    assert json.loads(embedded) == value
