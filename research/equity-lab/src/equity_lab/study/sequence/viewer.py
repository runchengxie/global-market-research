"""Self-contained private HTML projection; all data stays in the selected file."""

from datetime import date
from html import escape
from importlib.resources import files
import json
import math
import re
from pathlib import Path


def write_viewer(summary, path):
    if (
        summary.get("schema") != "equity_lab.sequence_diagnostics.v1"
        or summary.get("status") not in ["completed", "partial", "invalid", "running"]
        or not isinstance(summary.get("records"), list)
    ):
        raise ValueError("INVALID_DIAGNOSTIC_PROJECTION")
    for row in summary["records"]:
        if (
            not re.fullmatch("[a-z][a-z0-9_]*", row["model"])
            or type(row["fold"]) is not int
            or type(row["seed"]) is not int
        ):
            raise ValueError("INVALID_DIAGNOSTIC_PROJECTION")
        for day in row["dates"]:
            date.fromisoformat(day)
        for control, costs in row["accounts"].items():
            if control not in [
                "original",
                "constant_25",
                "constant_50",
                "validation_exposure",
                "validation_volatility",
                "causal_volatility_10",
                "validation_threshold",
            ]:
                raise ValueError("INVALID_DIAGNOSTIC_PROJECTION")
            for fee, account in costs.items():
                if (
                    fee not in ["0", "5", "20", "40"]
                    or not math.isfinite(account["return"])
                    or len(account["equity"]) != len(row["dates"])
                    or len(account["open_exposure"]) != len(row["dates"])
                    or any(not math.isfinite(v) or v <= 0 for v in account["equity"])
                    or any(
                        not math.isfinite(v) or not 0 <= v <= 1 + 1e-9
                        for v in account["open_exposure"]
                    )
                ):
                    raise ValueError("INVALID_DIAGNOSTIC_PROJECTION")
    assets = files("equity_lab.study.sequence").joinpath("templates")
    catalogs = {
        lang: json.loads(assets.joinpath(lang + ".json").read_text())
        for lang in ["en", "zh-CN"]
    }
    template = assets.joinpath("viewer.html").read_text()
    rows = []

    def percent(value):
        return "—" if value is None else f"{value:.2%}"

    for row in summary["records"]:
        account = row["accounts"].get("original", {}).get("5", {})
        values = [
            row["model"],
            row["fold"],
            row["seed"],
            percent(account.get("return")),
            percent(account.get("drawdown")),
            percent(account.get("exposure")),
            percent(account.get("realized_annual_volatility")),
            "",
        ]
        rows.append(
            "<tr>"
            + "".join("<td>" + escape(str(v)) + "</td>" for v in values)
            + "</tr>"
        )

    def encoded(value):
        return (
            json.dumps(value, allow_nan=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )

    template = (
        template.replace("__DATA_JSON__", encoded(summary))
        .replace("__CATALOGS__", encoded(catalogs))
        .replace("__FALLBACK_ROWS__", "".join(rows))
        .replace("__STATUS__", escape(summary["status"]))
        .replace(
            "__PROVENANCE__",
            escape(json.dumps(summary.get("provenance", {}), indent=2)),
        )
    )
    for key, value in catalogs["en"].items():
        template = template.replace("__LABEL_" + key + "__", escape(value))
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(template)
