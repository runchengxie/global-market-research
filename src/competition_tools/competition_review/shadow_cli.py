"""Manual offline prospective strategy workflow; no broker or scheduler."""

import argparse
from .shadow import prepare, record, evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["prepare", "record"]:
        p = sub.add_parser(name)
        p.add_argument("--case", required=True)
        p.add_argument("--output", required=True)
    p = sub.add_parser("evaluate")
    p.add_argument("--entry", required=True)
    p.add_argument("--outcome", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("nav")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command in {"prepare", "record"}:
        result = {"prepare": prepare, "record": record}[args.command](
            args.case, args.output
        )
    elif args.command == "evaluate":
        result = evaluate(args.entry, args.outcome, args.output)
    else:
        from .nav_change import explain_bundle

        result = explain_bundle(args.snapshot, args.output)
    print("Private offline artifact saved; no execution authorization.")
    return result


if __name__ == "__main__":
    main()
