"""Pinned cloc reports over committed Git files, with explicit program scopes."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

CLOC_SHA256 = "bf59272455172108072a0a106379f7509fd4349bdcfd85203bac038ccd286d83"
PROGRAM = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".astro",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sh",
    ".bash",
    ".ps1",
    ".bat",
    ".cmd",
    ".sql",
    ".r",
    ".rs",
    ".go",
    ".c",
    ".cc",
    ".h",
    ".cpp",
}
LOCKS = {"uv.lock", "package-lock.json"}


def group_report(files):
    groups = {}
    languages = {}
    other = 0
    for name, row in files.items():
        p = Path(name)
        parts = p.parts
        if p.suffix.lower() not in PROGRAM or name.startswith("site/src/data/"):
            other += row["code"]
            continue
        if "tests" in parts or p.name.endswith((".test.mjs", ".spec.mjs")):
            group = "tests"
        elif parts[0] == "src":
            group = "root_application"
        elif parts[0] == "research" and "src" in parts:
            group = "research/" + parts[1]
        elif parts[0] == "site":
            group = "site_application"
        else:
            group = "scripts_and_other_programs"
        groups[group] = groups.get(group, 0) + row["code"]
        languages[row["language"]] = languages.get(row["language"], 0) + row["code"]
    total = sum(groups.values())
    tests = groups.get("tests", 0)
    return dict(
        program_code=total,
        implementation_code=total - tests,
        test_code=tests,
        groups=groups,
        languages=languages,
        other_text_code_lines=other,
    )


def count_revision(root, cloc, revision="HEAD"):
    root = Path(root).resolve()
    cloc = Path(cloc).resolve()
    if hashlib.sha256(cloc.read_bytes()).hexdigest() != CLOC_SHA256:
        raise ValueError("UNEXPECTED_CLOC_BYTES")
    version = subprocess.check_output(
        ["perl", str(cloc), "--version"], text=True
    ).strip()
    if version != "2.10":
        raise ValueError("UNEXPECTED_CLOC_VERSION")
    sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", revision + "^{commit}"], text=True
    ).strip()
    with tempfile.TemporaryDirectory(prefix="gmr-cloc-") as temp:
        temp = Path(temp)
        archive = temp / "source.tar"
        export = temp / "source"
        export.mkdir()
        with archive.open("wb") as stream:
            subprocess.run(
                ["git", "-C", str(root), "archive", sha], stdout=stream, check=True
            )
        with tarfile.open(archive) as tar:
            if any(m.issym() or m.islnk() for m in tar.getmembers()):
                raise ValueError("SOURCE_SYMLINK_UNSUPPORTED")
            tar.extractall(export, filter="data")
        files = [p for p in export.rglob("*") if p.is_file() and p.name not in LOCKS]
        listing = temp / "files.txt"
        listing.write_text("\n".join(str(p) for p in files) + "\n")
        output = temp / "cloc.json"
        subprocess.run(
            [
                "perl",
                str(cloc),
                "--list-file=" + str(listing),
                "--by-file",
                "--json",
                "--skip-uniqueness",
                "--quiet",
                "--report-file=" + str(output),
            ],
            check=True,
        )
        raw = json.loads(output.read_text())
        relative = {
            str(Path(k).relative_to(export)): v
            for k, v in raw.items()
            if k not in ["header", "SUM"]
        }
    return dict(
        schema="competition.code_size.v1",
        revision=sha,
        tool=dict(name="cloc", version=version, sha256=CLOC_SHA256),
        **group_report(relative),
        all_recognized_text=raw["SUM"],
        files=relative,
        policy="Committed files; duplicates included; no lockfiles/dependencies/builds. Program excludes prose/config/data. Counts are not a quality gate.",
    )


def write_new(path, value):
    path = Path(path).absolute()
    if any((p / ".git").exists() for p in [path, *path.parents]):
        raise ValueError("REPORT_MUST_BE_EXTERNAL")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--source-root", type=Path, default=Path("."))
    p.add_argument("--cloc", type=Path, required=True)
    p.add_argument("--revision", default="HEAD")
    p.add_argument("--base")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = count_revision(args.source_root, args.cloc, args.revision)
    if args.base:
        base = count_revision(args.source_root, args.cloc, args.base)
        result["base_revision"] = base["revision"]
        result["delta"] = {
            k: result[k] - base[k]
            for k in [
                "program_code",
                "implementation_code",
                "test_code",
                "other_text_code_lines",
            ]
        }
    write_new(args.output, result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "revision",
                    "program_code",
                    "implementation_code",
                    "test_code",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
