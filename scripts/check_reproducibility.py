"""Run the generator twice (separate processes, separate folders) and compare every output file.

Each process gets its own Python hash seed, so any hidden dependence on set/dict ordering
would show up as different checksums. Writes reproducibility_report.md; exits 1 if anything differs.
"""
import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED = 20261022


def run_generator(scale: str, seed: int, out: Path) -> None:
    cmd = [sys.executable, "-m", "hrgen", "--scale", scale, "--seed", str(seed), "--out", str(out)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit(f"Generator failed: {' '.join(cmd)}")


def fingerprint(folder: Path) -> dict[str, tuple[str, int | None]]:
    """relative path -> (sha256, data rows for CSV files else None)."""
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            rel = path.relative_to(folder).as_posix()
            rows = data.count(b"\n") - 1 if rel.endswith(".csv") else None
            files[rel] = (hashlib.sha256(data).hexdigest(), rows)
    return files


def compare_scale(scale: str, seed: int) -> tuple[bool, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "run1", Path(tmp) / "run2"
        run_generator(scale, seed, a)
        run_generator(scale, seed, b)
        fa, fb = fingerprint(a), fingerprint(b)
    same_files = fa.keys() == fb.keys()
    lines = [f"## Scale `{scale}`", "",
             f"Command (run twice): `python -m hrgen --scale {scale} --seed {seed} --out <folder>`", "",
             "| File | Rows | SHA-256 run 1 | SHA-256 run 2 | Match |", "|---|---|---|---|---|"]
    all_match = same_files
    for rel in sorted(fa.keys() | fb.keys()):
        h1, h2 = fa.get(rel), fb.get(rel)
        match = h1 is not None and h1 == h2
        all_match &= match
        rows = "" if h1 is None or h1[1] is None else h1[1]
        lines.append(f"| {rel} | {rows} | {h1[0][:16] if h1 else 'missing'} | "
                     f"{h2[0][:16] if h2 else 'missing'} | {'yes' if match else 'NO'} |")
    lines += ["", f"Files compared: {len(fa)}. Verdict for `{scale}`: "
                  f"**{'IDENTICAL' if all_match else 'DIFFERENT'}**", ""]
    return all_match, lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Check that two seeded runs are identical")
    parser.add_argument("--scale", choices=["starter", "full", "all"], default="all")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--report", default=str(ROOT / "reproducibility_report.md"))
    args = parser.parse_args()

    scales = ["starter", "full"] if args.scale == "all" else [args.scale]
    report = ["# Reproducibility report", "",
              f"Seed `{args.seed}`. Each scale is generated twice in separate Python processes "
              "and every output file is compared by SHA-256 (first 16 hex characters shown; "
              "the comparison uses the full hash).", ""]
    everything = True
    for scale in scales:
        print(f"Running '{scale}' twice ...")
        ok, lines = compare_scale(scale, args.seed)
        everything &= ok
        report += lines
    verdict = "IDENTICAL" if everything else "DIFFERENT"
    report += [f"## Overall verdict: **{verdict}**", ""]
    Path(args.report).write_bytes("\n".join(report).encode("utf-8"))
    print(f"Verdict: {verdict} (report: {args.report})")
    raise SystemExit(0 if everything else 1)


if __name__ == "__main__":
    main()