#!/usr/bin/env python3
"""Run automated deployment preflight gate checks. Standard library only.

Evaluates all automated preflight gates before shipping:
1. Bugs: checks replica/bugs.md for 0 open S1 or S2 bugs
2. Parity: checks replica/features.csv for all must-haves and score threshold
3. Rebrand Sweep: runs sweep.py to verify codebase is clean of original brand identifiers
4. Store Listing: runs listing.py to check app store guidelines (if listing exists)
5. Production Build / Tests: executes configured test or build commands

Usage:
    python3 preflight.py
    python3 preflight.py --out replica/deploy.md --fail-under 80
    python3 preflight.py --run-tests --run-build
"""

import argparse
import datetime
import importlib.util
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_pack_root():
    curr = SCRIPT_DIR
    while curr and curr != os.path.dirname(curr):
        if os.path.isfile(os.path.join(curr, "plugin.json")) or os.path.isfile(os.path.join(curr, "README.md")):
            return curr
        curr = os.path.dirname(curr)
    return SCRIPT_DIR

PACK_ROOT = get_pack_root()


def load_module(rel_path, mod_name):
    candidates = [
        os.path.join(PACK_ROOT, "skills", rel_path),
        os.path.join(PACK_ROOT, rel_path),
        os.path.join(SCRIPT_DIR, rel_path.split("/")[-1]),
        os.path.join(SCRIPT_DIR, "..", rel_path.split("/")[-1]),
    ]
    for c in candidates:
        if os.path.isfile(c):
            spec = importlib.util.spec_from_file_location(mod_name, c)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def run_preflight(args):
    gates = []
    has_failure = False

    # 1. Bug Audit
    bugs_path = os.path.join(args.replica_dir, "bugs.md")
    check_bugs_mod = load_module("replica-test/scripts/check_bugs.py", "check_bugs")
    if os.path.isfile(bugs_path) and check_bugs_mod:
        bugs = check_bugs_mod.parse_bugs(bugs_path)
        stats = check_bugs_mod.audit_bugs(bugs)
        blocking = stats["by_sev"]["S1"]["open"] + stats["by_sev"]["S2"]["open"]
        if blocking == 0:
            gates.append({"name": "No open S1/S2 bugs", "pass": True, "detail": f"{stats['total']} bugs recorded, 0 open S1/S2"})
        else:
            gates.append({"name": "No open S1/S2 bugs", "pass": False, "detail": f"{blocking} blocking S1/S2 bug(s) open"})
            has_failure = True
    else:
        gates.append({"name": "No open S1/S2 bugs", "pass": True, "detail": "No bugs file found (0 known open bugs)"})

    # 2. Feature Parity
    matrix_path = os.path.join(args.replica_dir, "features.csv")
    parity_mod = load_module("replica-diff/scripts/parity.py", "parity") or load_module("replica-diff/parity.py", "parity")
    if os.path.isfile(matrix_path) and parity_mod:
        try:
            rows = parity_mod.load(matrix_path)
            res = parity_mod.score(rows)
            score_val = res.get("feature_score", 0.0)
            must_done = res.get("must_have_done", 0)
            must_tot = res.get("must_have_total", 0)

            all_must = (must_done == must_tot)
            score_ok = (score_val >= args.fail_under)
            passed = all_must and score_ok

            detail = f"Score {score_val:.1f} / 100, must-haves {must_done}/{must_tot} done"
            if not all_must:
                detail += f" ({must_tot - must_done} must-haves missing)"
            if not score_ok:
                detail += f" (under threshold {args.fail_under})"

            gates.append({"name": "Feature parity gate", "pass": passed, "detail": detail})
            if not passed:
                has_failure = True
        except Exception as exc:
            gates.append({"name": "Feature parity gate", "pass": False, "detail": f"Error: {exc}"})
            has_failure = True
    else:
        gates.append({"name": "Feature parity gate", "pass": False, "detail": f"Matrix file '{matrix_path}' not found"})
        has_failure = True

    # 3. Brand Rebrand Sweep
    brand_cfg = os.path.join(args.replica_dir, "brand.json")
    sweep_mod = load_module("replica-brand/scripts/sweep.py", "sweep") or load_module("replica-brand/sweep.py", "sweep")
    if os.path.isfile(brand_cfg) and sweep_mod:
        try:
            cfg = sweep_mod.load_config(brand_cfg)
            matches = sweep_mod.sweep(args.code_root, cfg)
            if not matches:
                gates.append({"name": "Rebrand sweep clean", "pass": True, "detail": f"0 target brand references found in {args.code_root}"})
            else:
                gates.append({"name": "Rebrand sweep clean", "pass": False, "detail": f"{len(matches)} reference(s) to original brand found in code"})
                has_failure = True
        except Exception as exc:
            gates.append({"name": "Rebrand sweep clean", "pass": False, "detail": f"Error: {exc}"})
            has_failure = True
    elif not os.path.isfile(brand_cfg):
        gates.append({"name": "Rebrand sweep clean", "pass": False, "detail": f"Brand config '{brand_cfg}' not found (run /replica-brand)"})
        has_failure = True
    else:
        gates.append({"name": "Rebrand sweep clean", "pass": False, "detail": "sweep.py tool not found"})
        has_failure = True

    # 4. Store Listing (if present)
    listing_path = os.path.join(args.replica_dir, "launch", "listing.json")
    listing_mod = load_module("replica-launch/scripts/listing.py", "listing") or load_module("replica-launch/listing.py", "listing")
    if os.path.isfile(listing_path) and listing_mod:
        try:
            data = listing_mod.load(listing_path)
            errs = listing_mod.lint(data)
            if not errs:
                gates.append({"name": "Store listing lint", "pass": True, "detail": "0 errors or rule violations"})
            else:
                gates.append({"name": "Store listing lint", "pass": False, "detail": f"{len(errs)} listing errors found"})
                has_failure = True
        except Exception as exc:
            gates.append({"name": "Store listing lint", "pass": False, "detail": f"Error: {exc}"})
            has_failure = True
    else:
        gates.append({"name": "Store listing lint", "pass": True, "detail": "Skipped (no store listing configured)"})

    # 5. Optional automated tests
    if args.run_tests:
        print("Running test suite...")
        res = subprocess.run(["npm", "test"], cwd=args.code_root, capture_output=True, text=True)
        if res.returncode == 0:
            gates.append({"name": "Automated tests", "pass": True, "detail": "Tests passed (exit 0)"})
        else:
            gates.append({"name": "Automated tests", "pass": False, "detail": f"npm test failed with exit code {res.returncode}"})
            has_failure = True

    # 6. Optional production build
    if args.run_build:
        print("Running production build...")
        res = subprocess.run(["npm", "run", "build"], cwd=args.code_root, capture_output=True, text=True)
        if res.returncode == 0:
            gates.append({"name": "Production build", "pass": True, "detail": "Build succeeded (exit 0)"})
        else:
            gates.append({"name": "Production build", "pass": False, "detail": f"npm run build failed with exit code {res.returncode}"})
            has_failure = True

    return gates, has_failure


def generate_deploy_md(gates, app_name="Clone"):
    today = datetime.date.today().isoformat()
    lines = [
        f"# Deploy checklist: {app_name}",
        "",
        f"Date: {today}  Preflight status: {'PASSED' if all(g['pass'] for g in gates) else 'FAILED'}",
        "",
        "## Automated Preflight Gates",
        "",
    ]

    for g in gates:
        chk = "[x]" if g["pass"] else "[ ]"
        lines.append(f"- {chk} **{g['name']}**: {g['detail']}")

    lines.extend([
        "",
        "## Manual Verification Gates",
        "",
        "- [ ] privacy policy and terms live, every processor listed",
        "- [ ] account deletion works as expected",
        "- [ ] favicon, titles, OG image, email templates, and app icons are verified",
        "",
        "## Production Services",
        "",
        "- [ ] separate production database, backups verified, migrations run",
        "- [ ] production environment variables set in hosting platform",
        "- [ ] Stripe live keys, products, prices, and webhook endpoint configured",
        "- [ ] OAuth redirect URIs and origins set for production domain",
        "- [ ] email sending domain verified (SPF, DKIM, DMARC)",
        "",
        "## Domain & Monitoring",
        "",
        "- [ ] DNS records configured and HTTPS certificate issued",
        "- [ ] error tracking and uptime monitoring active",
        "- [ ] core flow verified live on desktop and mobile",
        "",
    ])

    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--replica-dir", default="replica", help="replica planning directory (default: replica)")
    parser.add_argument("--code-root", default=".", help="project code root directory (default: .)")
    parser.add_argument("--out", default="replica/deploy.md", help="output checklist markdown file (default: replica/deploy.md)")
    parser.add_argument("--fail-under", type=float, default=80.0, help="feature parity minimum score threshold (default: 80)")
    parser.add_argument("--run-tests", action="store_true", help="run npm test")
    parser.add_argument("--run-build", action="store_true", help="run npm run build")
    parser.add_argument("--app-name", default="My Clone", help="app name for deploy checklist")
    args = parser.parse_args(argv)

    gates, has_failure = run_preflight(args)

    print("==================================================")
    print("DEPLOY PREFLIGHT GATE RESULTS")
    print("==================================================")
    for g in gates:
        status = "PASS" if g["pass"] else "FAIL"
        print(f"[{status}] {g['name']}: {g['detail']}")
    print("==================================================")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        content = generate_deploy_md(gates, app_name=args.app_name)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Wrote deployment checklist to {args.out}")

    if has_failure:
        print("\nGATE STATUS: BLOCKED. Address the failing gates before deploying.", file=sys.stderr)
        return 1

    print("\nGATE STATUS: GREEN. Ready for production deployment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
