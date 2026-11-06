"""Informational byte duplicates and declared Python imports; never dead-code proof."""

import argparse
import ast
import hashlib
from pathlib import Path
import subprocess
from .code_size import write_new


def inventory(root, files):
    root = Path(root).resolve()
    duplicates = {}
    modules = []
    for name in sorted(files):
        path = root / name
        if path.is_symlink() or not path.is_file():
            continue
        data = path.read_bytes()
        if data:
            key = hashlib.sha256(data).hexdigest()
            duplicates.setdefault(key, []).append(name)
        if path.suffix != ".py":
            continue
        tree = ast.parse(data.decode("utf-8-sig"), filename=name)
        imports = []
        entry = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            if isinstance(node, ast.ImportFrom):
                imports.append("." * node.level + (node.module or ""))
            if isinstance(node, ast.If) and isinstance(node.test, ast.Compare):
                test = node.test
                if (
                    isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"
                    and any(
                        isinstance(n, ast.Constant) and n.value == "__main__"
                        for n in test.comparators
                    )
                ):
                    entry = True
        modules.append(
            dict(
                path=name,
                physical_lines=len(data.splitlines()),
                static_declared_imports=sorted(set(imports)),
                entrypoint=entry,
                external_usage="unknown",
            )
        )
    return dict(
        schema="competition.source_inventory.v1",
        python_modules=modules,
        duplicate_groups=[
            dict(
                sha256=k,
                paths=v,
                interpretation="byte-identical; review ownership/semantics before extraction",
            )
            for k, v in duplicates.items()
            if len(v) > 1
        ],
        limitation="Dynamic/external use is not inferred; an unimported module may be a CLI or hashed experiment dependency. No removal recommendations are automatic.",
    )


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument("--source-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    names = (
        subprocess.check_output(["git", "-C", str(args.source_root), "ls-files", "-z"])
        .decode()
        .split("\0")
    )
    report = inventory(args.source_root, [n for n in names if n])
    report["revision"] = subprocess.check_output(
        ["git", "-C", str(args.source_root), "rev-parse", "HEAD"], text=True
    ).strip()
    write_new(args.output, report)
    print("Source inventory saved; duplicate groups:", len(report["duplicate_groups"]))


if __name__ == "__main__":
    main()
