#!/usr/bin/env python3
"""Screen brand name candidates for trademark search, domains, and store availability. Standard library only.

Evaluates name candidates against trademark screening portals, checks domain DNS
resolution, verifies avoidance rules, and produces a markdown table for replica/brand.md.

Usage:
    python3 check_brand.py Slotwise Booklink Calvo --avoid "Calendly"
    python3 check_brand.py Slotwise --category "appointment scheduler" --out replica/brand.md
"""

import argparse
import datetime
import os
import re
import socket
import sys
import urllib.parse


def check_dns_available(domain):
    """Check if domain resolves via DNS. If it fails resolution, it is likely available."""
    try:
        socket.getaddrinfo(domain, 80, proto=socket.IPPROTO_TCP)
        return False  # Resolves, so taken
    except (socket.gaierror, socket.herror, socket.timeout):
        return True  # Did not resolve, likely available or unconfigured


def generate_search_links(name, category="app"):
    q = urllib.parse.quote(name)
    q_cat = urllib.parse.quote(f"{name} {category}")
    return {
        "uspto": f"https://tmsearch.uspto.gov/search/search-results?search_type=quick&search_text={q}",
        "euipo": f"https://euipo.europa.eu/eSearch/#basic/1+1+1+1/{q}",
        "wipo": f"https://branddb.wipo.int/en/quicksearch?q={q}",
        "github": f"https://github.com/{q}",
        "app_store": f"https://www.google.com/search?q=site%3Aapps.apple.com+{q}",
        "google_play": f"https://play.google.com/store/search?q={q}&c=apps",
        "web": f"https://www.google.com/search?q={q_cat}",
    }


def evaluate_candidate(name, avoid_list=None, category="app"):
    avoid_list = avoid_list or []
    name_clean = name.strip()
    warnings = []

    if len(name_clean) < 3:
        warnings.append("too short (< 3 chars)")
    if len(name_clean) > 20:
        warnings.append("too long (> 20 chars)")
    if not re.match(r"^[A-Za-z0-9]+$", name_clean):
        warnings.append("contains symbols/punctuation")

    for avoid in avoid_list:
        avoid_norm = avoid.strip().lower()
        if not avoid_norm:
            continue
        if avoid_norm in name_clean.lower():
            warnings.append(f"contains target brand '{avoid}'")
        elif name_clean.lower() in avoid_norm:
            warnings.append(f"too close to target brand '{avoid}'")

    # Domain checks
    tlds = [".com", ".io", ".app", ".dev"]
    domains = {}
    for tld in tlds:
        dom = f"{name_clean.lower()}{tld}"
        avail = check_dns_available(dom)
        domains[dom] = "likely available" if avail else "registered"

    links = generate_search_links(name_clean, category=category)

    return {
        "name": name_clean,
        "warnings": warnings,
        "domains": domains,
        "links": links,
    }


def render_brand_report(candidates_data):
    today = datetime.date.today().isoformat()
    lines = [
        "## Brand Name Candidate Screening",
        f"Screened on: {today}",
        "",
        "| Candidate | Status | Domains | Trademark Screening Links |",
        "| --- | --- | --- | --- |",
    ]

    for c in candidates_data:
        name = c["name"]
        status = "Needs clearance" if not c["warnings"] else ("Caution: " + ", ".join(c["warnings"]))
        dom_summary = ", ".join(f"{d} ({s})" for d, s in list(c["domains"].items())[:2])
        links = c["links"]
        tm_links = f"[USPTO]({links['uspto']}) | [EUIPO]({links['euipo']}) | [WIPO]({links['wipo']}) | [Store]({links['app_store']})"
        lines.append(f"| **{name}** | {status} | {dom_summary} | {tm_links} |")

    lines.append("")
    lines.append("> Note: These are initial automated screening checks. Official clearance requires review by a qualified trademark professional.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("names", nargs="+", help="candidate brand names to screen")
    parser.add_argument("--avoid", default="", help="comma-separated target app names/brands to avoid")
    parser.add_argument("--category", default="app", help="app category for web searches")
    parser.add_argument("--out", help="optional output file path to write markdown report")
    args = parser.parse_args(argv)

    avoid_list = [a.strip() for a in args.avoid.split(",") if a.strip()]
    results = [evaluate_candidate(n, avoid_list=avoid_list, category=args.category) for n in args.names]
    report = render_brand_report(results)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "a" if os.path.isfile(args.out) else "w", encoding="utf-8") as f:
            f.write("\n\n" + report + "\n")
        print(f"Appended brand candidate screening to {args.out}")
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
