import argparse
from pathlib import Path

from . import ids
from .config import DEFAULT_SEED, SCALES
from .export import GROUND_TRUTH_TABLES, TABLE_ORDER, export_all
from .metrics import compute_metrics, format_metrics
from .pipeline import generate


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic HR helpdesk data generator")
    parser.add_argument("--scale", choices=list(SCALES), default="starter")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default=None, help="output folder")
    args = parser.parse_args()

    scale = SCALES[args.scale]
    out = Path(args.out or f"output/{args.scale}")

    print(f"Generating '{scale.name}' with seed {args.seed} into {out}")
    print("Example IDs:", ids.ticket_id(1), ids.version_id(ids.policy_id(1), 1),
          ids.message_id(ids.ticket_id(1), 1))

    tables, truth = generate(scale, args.seed)
    metrics = compute_metrics(tables, truth)
    manifest = export_all(out, tables, truth, metrics, scale.name, args.seed)

    for name in TABLE_ORDER:
        print(f"  {name}: {manifest['row_counts'][name]} rows")
    for name in GROUND_TRUTH_TABLES:
        print(f"  ground_truth/{name}: {manifest['ground_truth_row_counts'][name]} rows")
    print(format_metrics(metrics))
    print(f"Wrote {len(manifest['files']) + 1} files (see {out / 'manifest.json'})")


if __name__ == "__main__":
    main()