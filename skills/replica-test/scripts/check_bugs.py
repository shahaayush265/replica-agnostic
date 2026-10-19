#!/usr/bin/env python3
"""Bug tracker audit and gate check for replica-test and replica-deploy. Standard library only.

Parses replica/bugs.md, tabulates bugs by severity (S1 to S4) and status (open vs fixed),
and gates deployment by ensuring no S1 or S2 bugs remain open.

Severity definitions:
    S1: data loss, security hole, payments wrong, core flow blocked
    S2: a feature broken, no workaround
    S3: broken with a workaround, or visibly wrong
    S4: cosmetic

Usage:
    python3 check_bugs.py replica/bugs.md
    python3 check_bugs.py --fail-on-blocking     # exits 1 if any S1 or S2 is open
"""

import argparse
import os
import re
import sys


def parse_bugs(path):
    if not os.path.isfile(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    bug_blocks = re.split(r"(?m)^(?=###\s+BUG-)", text)
    bugs = []

    for block in bug_blocks:
        block = block.strip()
        if not block.startswith("### BUG-"):
            continue

        title_m = re.match(r"^###\s+(BUG-[A-Za-z0-9_-]+):\s*(.*)", block)
        if not title_m:
            continue
        bug_id = title_m.group(1)
        title = title_m.group(2).strip()

        sev_m = re.search(r"(?i)-\s*Severity:\s*([sS][1-4])", block)
        severity = sev_m.group(1).upper() if sev_m else "S3"

        status_m = re.search(r"(?i)-\s*Status:\s*([^\n]+)", block)
        raw_status = status_m.group(1).strip() if status_m else "open"

        is_open = True
        status_lower = raw_status.lower()
        if any(w in status_lower for w in ("fixed", "closed", "resolved", "won't fix", "wont fix")):
            is_open = False

        bugs.append({
            "id": bug_id,
            "title": title,
            "severity": severity,
            "status": raw_status,
            "is_open": is_open,
        })

    return bugs


def audit_bugs(bugs):
    stats = {
        "total": len(bugs),
        "open": 0,
        "fixed": 0,
        "by_sev": {"S1": {"open": 0, "fixed": 0},
                   "S2": {"open": 0, "fixed": 0},
                   "S3": {"open": 0, "fixed": 0},
                   "S4": {"open": 0, "fixed": 0}},
    }

    for b in bugs:
        sev = b["severity"] if b["severity"] in stats["by_sev"] else "S3"
        if b["is_open"]:
            stats["open"] += 1
            stats["by_sev"][sev]["open"] += 1
        else:
            stats["fixed"] += 1
            stats["by_sev"][sev]["fixed"] += 1

    return stats


def render_report(bugs, stats):
    lines = []
    lines.append(f"Bug Audit: {stats['total']} total bugs ({stats['open']} open, {stats['fixed']} fixed)")
    lines.append("")
    lines.append("Severity  Open  Fixed")
    for sev in ("S1", "S2", "S3", "S4"):
        s = stats["by_sev"][sev]
        lines.append(f"  {sev:6}  {s['open']:4}  {s['fixed']:5}")

    open_blocking = [b for b in bugs if b["is_open"] and b["severity"] in ("S1", "S2")]
    if open_blocking:
        lines.append("")
        lines.append("Blocking Open Bugs (S1 / S2):")
        for b in open_blocking:
            lines.append(f"  [{b['severity']}] {b['id']}: {b['title']} (Status: {b['status']})")
    else:
        lines.append("")
        lines.append("No open S1 or S2 blocking bugs. Shippable.")

    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("bugs_file", nargs="?", default="replica/bugs.md",
                        help="path to replica/bugs.md (default: replica/bugs.md)")
    parser.add_argument("--fail-on-blocking", action="store_true",
                        help="exit with code 1 if any S1 or S2 bug is open")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.bugs_file):
        print(f"check_bugs: file '{args.bugs_file}' not found (0 bugs recorded).")
        return 0

    bugs = parse_bugs(args.bugs_file)
    stats = audit_bugs(bugs)
    print(render_report(bugs, stats))

    blocking_open = stats["by_sev"]["S1"]["open"] + stats["by_sev"]["S2"]["open"]
    if args.fail_on_blocking and blocking_open > 0:
        print(f"\nGATE BLOCKED: {blocking_open} S1/S2 bug(s) still open.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
