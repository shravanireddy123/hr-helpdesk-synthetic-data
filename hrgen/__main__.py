import argparse
import random
from pathlib import Path

import pandas as pd
from faker import Faker

from . import ids
from .anomalies import CHANGED_TABLES, inject_anomalies
from .config import DEFAULT_SEED, SCALES
from .master_data import build_master_data
from .messages import build_messages
from .sla import build_sla
from .tickets import build_tickets


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic HR helpdesk data generator")
    parser.add_argument("--scale", choices=list(SCALES), default="starter")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default=None, help="output folder")
    args = parser.parse_args()

    scale = SCALES[args.scale]
    out = Path(args.out or f"output/{args.scale}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "ground_truth").mkdir(exist_ok=True)

    rng = random.Random(args.seed)   # the ONLY source of randomness
    fake = Faker("en_IN")
    fake.seed_instance(args.seed)

    print(f"Generating '{scale.name}' with seed {args.seed} into {out}")
    print("Example IDs:", ids.ticket_id(1), ids.version_id(ids.policy_id(1), 1),
          ids.message_id(ids.ticket_id(1), 1))

    tables = build_master_data(rng, fake, scale)
    tables.update(build_tickets(rng, tables["employee"], scale))
    msg = build_messages(rng, tables, tables, scale)
    tables["message"] = msg["message"]
    tables["message_citation"] = msg["message_citation"]
    tables["ticket_status_event"] = sorted(
        tables["ticket_status_event"] + msg["new_events"], key=lambda e: e["event_id"])
    tables.update(build_sla(tables))      # derived: no rng; adds escalations

    anomalies = inject_anomalies(rng, tables)          # corrupt LAST, label everything
    tables.update({name: anomalies[name] for name in CHANGED_TABLES})

    for name, rows in tables.items():
        # TEMPORARY: export.py will replace these CSV lines.
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False, lineterminator="\n")
        print(f"  {name}: {len(rows)} rows")
    for name in ("ground_truth", "expected_decisions"):
        pd.DataFrame(anomalies[name]).to_csv(out / "ground_truth" / f"{name}.csv",
                                             index=False, lineterminator="\n")
        print(f"  ground_truth/{name}: {len(anomalies[name])} rows")

    counts: dict[str, int] = {}
    for g in anomalies["ground_truth"]:
        counts[g["issue_type"]] = counts.get(g["issue_type"], 0) + 1
    print("  anomalies:", dict(sorted(counts.items())))


if __name__ == "__main__":
    main()