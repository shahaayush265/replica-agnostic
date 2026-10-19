#!/usr/bin/env python3
"""Run batch screenshot layout diffs and compute overall parity report. Standard library only.

Finds matching screenshot pairs between original screens and clone screens:
    replica/screens/<id>.png <-> replica/clone-screens/<id>.png

Runs imgdiff.py on each pair, generates diff images and JSON metrics into
replica/diffs/, and invokes parity.py with all visual diffs to update replica/parity.md.

Usage:
    python3 batch_diff.py
    python3 batch_diff.py --matrix replica/features.csv --fail-under 80
    python3 batch_diff.py --out replica/parity.md
"""

import argparse
import glob
import importlib.util
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_script(name):
    path = os.path.join(SCRIPT_DIR, name + ".py")
    if not os.path.isfile(path):
        path = os.path.join(SCRIPT_DIR, "..", name + ".py")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Could not find {name}.py in {SCRIPT_DIR}")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_screen_pairs(orig_dir, clone_dir):
    pairs = []
    if not os.path.isdir(orig_dir) or not os.path.isdir(clone_dir):
        return pairs

    orig_files = os.listdir(orig_dir)
    for f in sorted(orig_files):
        if not f.lower().endswith(".png"):
            continue
        orig_path = os.path.join(orig_dir, f)
        clone_path = os.path.join(clone_dir, f)
        if os.path.isfile(clone_path):
            screen_id = os.path.splitext(f)[0]
            pairs.append((screen_id, orig_path, clone_path))
    return pairs


def run_batch(matrix_path, orig_dir, clone_dir, diff_dir, out_md, fail_under=None):
    os.makedirs(diff_dir, exist_ok=True)
    imgdiff_mod = load_script("imgdiff")
    parity_mod = load_script("parity")

    pairs = find_screen_pairs(orig_dir, clone_dir)
    diff_json_files = []

    print(f"Found {len(pairs)} matching screenshot pair(s) between {orig_dir} and {clone_dir}")
    for screen_id, orig_path, clone_path in pairs:
        out_png = os.path.join(diff_dir, f"{screen_id}-diff.png")
        out_json = os.path.join(diff_dir, f"{screen_id}.json")

        # Run imgdiff directly
        try:
            r = imgdiff_mod.compare(orig_path, clone_path, mode="layout", width=480)
            imgdiff_mod.render_diff(r, out_png)
            diff_data = {
                "score": r["score"],
                "mode": r["mode"],
                "height_diff": r["height_diff"],
                "regions": r["regions"],
                "files": {"original": orig_path, "clone": clone_path, "diff": out_png},
            }
            with open(out_json, "w", encoding="utf-8") as jf:
                json.dump(diff_data, jf, indent=2)
            diff_json_files.append(out_json)
            print(f"  {screen_id}: layout score {r['score']:.1f} -> {out_png}")
        except Exception as exc:
            print(f"  {screen_id}: failed diff: {exc}", file=sys.stderr)

    if not os.path.isfile(matrix_path):
        print(f"batch_diff: feature matrix '{matrix_path}' not found", file=sys.stderr)
        return 2

    # Run parity calculation
    try:
        rows = parity_mod.load(matrix_path)
        base_result = parity_mod.score(rows)
        visuals = parity_mod.visual_scores(diff_json_files) if diff_json_files else []
        final_result = parity_mod.combine(base_result, visuals)
        report_md = parity_mod.render(final_result, markdown=True)
    except Exception as exc:
        print(f"batch_diff: parity calculation error: {exc}", file=sys.stderr)
        return 2

    if out_md:
        os.makedirs(os.path.dirname(os.path.abspath(out_md)), exist_ok=True)
        with open(out_md, "w", encoding="utf-8") as mf:
            mf.write(report_md + "\n")
        print(f"\nWrote full parity report to {out_md}")
    else:
        print("\n" + report_md)

    overall = final_result.get("overall", 0.0)
    print(f"Overall parity score: {overall:.1f} / 100")

    if fail_under is not None and overall < fail_under:
        print(f"FAILED: overall score {overall:.1f} is under threshold {fail_under:.1f}", file=sys.stderr)
        return 1

    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--matrix", default="replica/features.csv",
                        help="feature matrix CSV (default: replica/features.csv)")
    parser.add_argument("--orig-screens", default="replica/screens",
                        help="directory with original screenshots (default: replica/screens)")
    parser.add_argument("--clone-screens", default="replica/clone-screens",
                        help="directory with clone screenshots (default: replica/clone-screens)")
    parser.add_argument("--diff-dir", default="replica/diffs",
                        help="directory to save diff PNGs and JSONs (default: replica/diffs)")
    parser.add_argument("--out", default="replica/parity.md",
                        help="markdown report output path (default: replica/parity.md)")
    parser.add_argument("--fail-under", type=float, help="exit code 1 if overall score is under this threshold")
    args = parser.parse_args(argv)

    return run_batch(
        matrix_path=args.matrix,
        orig_dir=args.orig_screens,
        clone_dir=args.clone_screens,
        diff_dir=args.diff_dir,
        out_md=args.out,
        fail_under=args.fail_under,
    )


if __name__ == "__main__":
    sys.exit(main())
