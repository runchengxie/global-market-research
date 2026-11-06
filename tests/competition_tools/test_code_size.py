from competition_tools.code_size import group_report
from competition_tools.source_inventory import inventory


def test_code_groups_exclude_data_locks_and_separate_tests(tmp_path):
    files = {
        "src/a.py": {"code": 10, "language": "Python"},
        "tests/test_a.py": {"code": 20, "language": "Python"},
        "site/src/data/export.mjs": {"code": 1000, "language": "JavaScript"},
        "docs/x.md": {"code": 100, "language": "Markdown"},
        "research/equity-lab/src/equity_lab/m.py": {"code": 5, "language": "Python"},
    }
    result = group_report(files)
    assert result["program_code"] == 35
    assert result["implementation_code"] == 15 and result["test_code"] == 20


def test_inventory_records_cli_and_duplicates_without_declaring_dead_code(tmp_path):
    for name in ["src/a.py", "research/equity-lab/src/equity_lab/a.py"]:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('import json\nif __name__ == "__main__":\n    print(1)\n')
    result = inventory(
        tmp_path, ["src/a.py", "research/equity-lab/src/equity_lab/a.py"]
    )
    assert len(result["duplicate_groups"]) == 1
    assert all(row["entrypoint"] for row in result["python_modules"])
    assert all(row["external_usage"] == "unknown" for row in result["python_modules"])
