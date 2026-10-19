#!/usr/bin/env python3
"""Generate test plan and E2E test stubs from recon flows. Standard library only.

Reads replica/recon.md, parses flows (F01, F02, etc.), and generates:
1. replica/test-plan.md with happy path, edge cases, and negative cases
2. Optional Playwright test stubs in e2e/

Usage:
    python3 generate_test_plan.py
    python3 generate_test_plan.py --recon replica/recon.md --out replica/test-plan.md
    python3 generate_test_plan.py --scaffold-e2e
"""

import argparse
import datetime
import os
import re
import sys


def parse_flows(recon_path):
    if not os.path.isfile(recon_path):
        return []

    with open(recon_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Look for flow declarations like:
    # F01 Guest books a meeting
    # or ### F01 Guest books a meeting
    flow_pattern = re.compile(
        r"(?:^|\n)(?:###\s*)?(F\d+)\s+([^\n\r]+)(?:\n\s*([S\d\s\->]+))?(?:\n\s*happy path clicks:\s*(\d+))?(?:\n\s*edge:\s*([^\n\r]+))?",
        re.MULTILINE
    )

    flows = []
    for m in flow_pattern.finditer(content):
        fid = m.group(1).strip()
        goal = m.group(2).strip()
        screens = m.group(3).strip() if m.group(3) else ""
        clicks = m.group(4).strip() if m.group(4) else "3"
        edges = m.group(5).strip() if m.group(5) else ""

        flows.append({
            "id": fid,
            "goal": goal,
            "screens": screens,
            "clicks": clicks,
            "edges": edges,
        })

    return flows


def build_test_plan(flows, app_name="Clone"):
    date_str = datetime.date.today().isoformat()
    lines = [
        f"# Test plan: {app_name}",
        "",
        f"Generated: {date_str}  Env: local, seed data",
        "",
        "| case | flow | type | steps | expected | auto | result |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for fl in flows:
        fid = fl["id"]
        goal = fl["goal"]
        screens_desc = f" ({fl['screens']})" if fl["screens"] else ""

        # Happy path
        lines.append(f"| {fid}-H1 | {goal} | happy | Complete flow end to end{screens_desc} | Success screen and database record created | e2e | |")

        # Standard edge cases
        lines.append(f"| {fid}-E1 | {goal} | edge | Submit empty and boundary length fields | Validation messages displayed, submission prevented | e2e | |")
        lines.append(f"| {fid}-E2 | {goal} | edge | Rapid double click on submit button | Exactly one record created, no duplicate actions | e2e | |")
        lines.append(f"| {fid}-E3 | {goal} | edge | Mobile viewport 390px layout test | Responsive elements stacked, no horizontal scroll | e2e | |")
        lines.append(f"| {fid}-E4 | {goal} | edge | Accessibility axe-core scan on each screen | Zero WCAG 2.1 AA violations | e2e | |")

        # If custom edges listed in recon
        if fl["edges"]:
            for i, custom_edge in enumerate(fl["edges"].split(","), start=5):
                custom_edge = custom_edge.strip()
                if custom_edge:
                    lines.append(f"| {fid}-E{i} | {goal} | edge: {custom_edge} | Verify behavior under {custom_edge} | Graceful recovery or correct state transition | manual | |")

        # Negative cases
        lines.append(f"| {fid}-N1 | {goal} | negative | Unauthenticated request or expired session | Redirected to sign in without losing state | e2e | |")
        lines.append(f"| {fid}-N2 | {goal} | negative | Access another user's private data in flow | 403 Forbidden or 404 Not Found returned | e2e | |")

    lines.append("")
    return "\n".join(lines)


def scaffold_playwright_test(flow, out_dir="e2e"):
    os.makedirs(out_dir, exist_ok=True)
    fid = flow["id"].lower()
    spec_path = os.path.join(out_dir, f"{fid}_{re.sub(r'[^a-z0-9]+', '_', flow['goal'].lower()).strip('_')}.spec.ts")

    content = f"""import {{ test, expect }} from '@playwright/test';

test.describe('{flow["id"]}: {flow["goal"]}', () => {{
  test('{flow["id"]}-H1 happy path: complete flow', async ({{ page }}) => {{
    const errors: string[] = [];
    page.on('console', msg => {{
      if (msg.type() === 'error') errors.push(msg.text());
    }});

    await page.goto('/');
    // TODO: implement flow steps for {flow["goal"]}
    // await page.getByRole('button', {{ name: 'Continue' }}).click();

    expect(errors).toHaveLength(0);
  }});

  test('{flow["id"]}-E1 validation on empty submit', async ({{ page }}) => {{
    await page.goto('/');
    // TODO: verify validation states
  }});

  test('{flow["id"]}-E3 responsive layout at 390px', async ({{ page }}) => {{
    await page.setViewportSize({{ width: 390, height: 844 }});
    await page.goto('/');
    // TODO: check mobile responsiveness
  }});
}});
"""
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(content)
    return spec_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--recon", default="replica/recon.md", help="path to recon.md (default: replica/recon.md)")
    parser.add_argument("--out", default="replica/test-plan.md", help="output path for test plan (default: replica/test-plan.md)")
    parser.add_argument("--app-name", default="My Clone", help="app name for test plan title")
    parser.add_argument("--scaffold-e2e", action="store_true", help="also generate starter Playwright specs in e2e/")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.recon):
        print(f"generate_test_plan: recon file '{args.recon}' not found", file=sys.stderr)
        return 2

    flows = parse_flows(args.recon)
    if not flows:
        # Fallback if no flows parsed specifically
        flows = [{"id": "F01", "goal": "Core user loop", "screens": "S01 -> S02", "clicks": "3", "edges": "offline, latency"}]

    plan_md = build_test_plan(flows, app_name=args.app_name)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(plan_md)
    print(f"Generated test plan with {len(flows)} flows at {args.out}")

    if args.scaffold_e2e:
        for fl in flows:
            p = scaffold_playwright_test(fl)
            print(f"  scaffolded spec: {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
