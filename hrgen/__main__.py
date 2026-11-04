import argparse
import random
from pathlib import Path

from faker import Faker

from . import ids
from .config import DEFAULT_SEED, SCALES


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic HR helpdesk data generator")
    parser.add_argument("--scale", choices=list(SCALES), default="starter")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", default=None, help="output folder")
    args = parser.parse_args()

    scale = SCALES[args.scale]
    out = Path(args.out or f"output/{args.scale}")
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)   # the ONLY source of randomness
    fake = Faker("en_IN")
    fake.seed_instance(args.seed)

    print(f"Generating '{scale.name}' with seed {args.seed} into {out}")
    print("Example IDs:", ids.ticket_id(1), ids.version_id(ids.policy_id(1), 1),
          ids.message_id(ids.ticket_id(1), 1))


if __name__ == "__main__":
    main()