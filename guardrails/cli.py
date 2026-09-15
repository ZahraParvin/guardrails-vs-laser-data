import argparse
from dataclasses import fields
import json
import requests
from pathlib import Path

from .analysis import Settings, run
from .demo import make_demo
from .io import fetch, inspect_las


def main():
    parser = argparse.ArgumentParser(description="Compare guardrail lines with laser data in EPSG:25833")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_parser = commands.add_parser("fetch", help="Download NVDB type 5 and preserve raw metadata")
    fetch_parser.add_argument("--bbox", required=True, help="minx,miny,maxx,maxy in EPSG:25833")
    fetch_parser.add_argument("--output", default="data/nvdb")
    fetch_parser.add_argument("--client", default="guardrails-vs-laser-data")
    inspect_parser = commands.add_parser("inspect", help="Inspect LAS/LAZ metadata and classes in chunks")
    inspect_parser.add_argument("tile")
    run_parser = commands.add_parser("run", help="Crop, analyse and export results")
    run_parser.add_argument("--guardrails", required=True)
    run_parser.add_argument("--tile", required=True)
    run_parser.add_argument("--reference-guardrails", help="All nearby registered guardrails for candidate exclusion, including other roads")
    run_parser.add_argument("--output", default="outputs/real")
    run_parser.add_argument("--config", help="JSON settings overrides")
    demo_parser = commands.add_parser("demo", help="Generate and analyse deterministic synthetic data")
    demo_parser.add_argument("--output", default="outputs/demo")
    review_parser = commands.add_parser("review", help="Summarise a completed manual review CSV")
    review_parser.add_argument("csv")
    args = parser.parse_args()
    try:
        if args.command == "fetch":
            frame = fetch(args.bbox, args.output, args.client)
            print(f"Saved {len(frame)} guardrails, {frame.length.sum():.1f} metres")
        elif args.command == "inspect":
            print(json.dumps(inspect_las(args.tile), indent=2))
        elif args.command == "demo":
            lines, tile = make_demo(Path(args.output) / "inputs")
            print(json.dumps(run(lines, tile, args.output, Settings(), synthetic=True), indent=2))
        elif args.command == "review":
            import pandas as pd
            review = pd.read_csv(args.csv).fillna("")
            allowed = {"", "confirmed", "false_positive", "uncertain"}
            if not set(review.verdict).issubset(allowed):
                raise ValueError("verdict must be confirmed, false_positive, uncertain or blank")
            print(json.dumps(dict(total=len(review), reviewed=int((review.verdict != "").sum()),
                                  verdicts=review.verdict.replace("", "unreviewed").value_counts().to_dict()), indent=2))
        else:
            overrides = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {}
            unknown = set(overrides) - {field.name for field in fields(Settings)}
            if unknown:
                raise ValueError(f"Unknown settings: {unknown}")
            print(json.dumps(run(args.guardrails, args.tile, args.output, Settings(**overrides),
                                 reference_lines_path=args.reference_guardrails), indent=2))
    except (ValueError, OSError, KeyError, requests.RequestException) as error:
        parser.exit(2, f"Error: {error}\n")
