#!/usr/bin/env python3
"""Unified CLI for the Replica skill pack in Antigravity. Standard library only.

Provides convenient commands for every automated task in the clone workflow:
    python3 replica.py init           Initialize workspace and templates
    python3 replica.py fetch-reviews  Fetch public reviews from App Store / HN
    python3 replica.py reviews        Analyze and rank complaints
    python3 replica.py build-tokens   Compile tokens.json to CSS and Tailwind
    python3 replica.py contrast       Run WCAG contrast checks on tokens
    python3 replica.py test-plan      Generate test plan from recon flows
    python3 replica.py check-bugs     Check for open blocking S1/S2 bugs
    python3 replica.py diff           Run batch screenshot layout diffs & parity
    python3 replica.py parity         Compute feature parity score
    python3 replica.py check-brand    Screen brand candidate names & domains
    python3 replica.py sweep          Scan codebase for original brand leaks
    python3 replica.py listing        Lint store listing limits and claims
    python3 replica.py preflight      Run full automated deployment gate check
"""

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def dispatch(script_rel, argv):
    # Try skills/<folder>/scripts/<script>.py or skills/<folder>/<script>.py
    candidates = [
        os.path.join(SCRIPT_DIR, "skills", script_rel),
        os.path.join(SCRIPT_DIR, script_rel),
    ]
    target = None
    for c in candidates:
        if os.path.isfile(c):
            target = c
            break

    if not target:
        print(f"replica: helper script not found: {script_rel}", file=sys.stderr)
        return 2

    import importlib.util
    spec = importlib.util.spec_from_file_location("replica_subcommand", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "main"):
        return mod.main(argv)
    return 0


def main():
    commands = {
        "init": ("replica-recon/scripts/init_replica.py", "Initialize workspace and templates"),
        "fetch-reviews": ("replica-entrepreneur/scripts/fetch_reviews.py", "Fetch public reviews from App Store or HN"),
        "reviews": ("replica-entrepreneur/scripts/reviews.py", "Rank complaints into themes"),
        "build-tokens": ("replica-design/scripts/build_tokens.py", "Compile tokens.json to CSS and Tailwind"),
        "contrast": ("replica-design/scripts/contrast.py", "WCAG contrast ratio checker"),
        "test-plan": ("replica-test/scripts/generate_test_plan.py", "Generate test plan from recon flows"),
        "check-bugs": ("replica-test/scripts/check_bugs.py", "Audit bugs and check for blocking issues"),
        "diff": ("replica-diff/scripts/batch_diff.py", "Batch screenshot diff and parity report"),
        "parity": ("replica-diff/scripts/parity.py", "Feature parity matrix calculator"),
        "imgdiff": ("replica-diff/scripts/imgdiff.py", "Screenshot layout comparison"),
        "check-brand": ("replica-brand/scripts/check_brand.py", "Screen brand names and domains"),
        "sweep": ("replica-brand/scripts/sweep.py", "Scan codebase for original brand identifiers"),
        "listing": ("replica-launch/scripts/listing.py", "Lint App Store and Play Store listing"),
        "preflight": ("replica-deploy/scripts/preflight.py", "Run full deployment gate checks"),
    }

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("Available subcommands:")
        for cmd, (_, desc) in sorted(commands.items()):
            print(f"  {cmd:15} {desc}")
        return 0

    cmd = sys.argv[1]
    if cmd not in commands:
        print(f"replica: unknown subcommand '{cmd}'. Run with --help for list.", file=sys.stderr)
        return 2

    script_rel, _ = commands[cmd]
    return dispatch(script_rel, sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
