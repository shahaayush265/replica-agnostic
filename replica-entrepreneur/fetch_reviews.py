#!/usr/bin/env python3
"""Fetch public app reviews and discussions into replica/reviews.csv. Standard library only.

Pulls real reviews and user complaints from public sources without requiring private
API keys or browser scraping:

1. Apple App Store customer reviews RSS feed (JSON format)
2. Hacker News Algolia search API (discussions and complaints)

Usage:
    python3 fetch_reviews.py --app-id 1459203874 --out replica/reviews.csv
    python3 fetch_reviews.py --hn-query "Calendly alternative" --append
    python3 fetch_reviews.py --app-id 1459203874 --hn-query "Calendly complaints"

Columns written:
    source,url,date,rating,text
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


def strip_html(html_text):
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = re.sub(r"&[a-zA-Z0-9#]+;", " ", clean)
    return " ".join(clean.split())


def fetch_apple_reviews(app_id, limit=50):
    url = f"https://itunes.apple.com/us/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
    req = urllib.request.Request(url, headers={"User-Agent": "ReplicaSkill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"Warning: could not fetch Apple App Store reviews: {exc}", file=sys.stderr)
        return []

    feed = data.get("feed", {})
    entries = feed.get("entry", [])
    if not isinstance(entries, list):
        entries = [entries] if entries else []

    reviews = []
    # Note: first entry in RSS feed is often the application itself
    for entry in entries:
        if "im:rating" not in entry:
            continue
        try:
            rating = entry.get("im:rating", {}).get("label", "")
            title = entry.get("title", {}).get("label", "").strip()
            content = entry.get("content", {}).get("label", "").strip()
            text = f"{title}. {content}" if title and content else (content or title)
            text = " ".join(text.split())

            raw_date = entry.get("updated", {}).get("label", "")
            date = raw_date[:10] if len(raw_date) >= 10 else ""

            link = entry.get("link", {}).get("attributes", {}).get("href", "")
            if not link:
                link = f"https://apps.apple.com/app/id{app_id}"

            if text and link:
                reviews.append({
                    "source": "App Store",
                    "url": link,
                    "date": date,
                    "rating": rating,
                    "text": text,
                })
        except Exception:
            continue
        if len(reviews) >= limit:
            break

    return reviews


def fetch_hn_discussions(query, limit=50):
    encoded = urllib.parse.quote(query)
    url = f"https://hn.algolia.com/api/v1/search?query={encoded}&tags=comment&hitsPerPage={min(limit, 100)}"
    req = urllib.request.Request(url, headers={"User-Agent": "ReplicaSkill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"Warning: could not fetch Hacker News discussions: {exc}", file=sys.stderr)
        return []

    hits = data.get("hits", [])
    reviews = []
    for hit in hits:
        raw_text = hit.get("comment_text", "")
        text = strip_html(raw_text)
        if not text or len(text) < 20:
            continue
        created = hit.get("created_at", "")
        date = created[:10] if len(created) >= 10 else ""
        item_id = hit.get("objectID") or hit.get("story_id")
        link = f"https://news.ycombinator.com/item?id={item_id}" if item_id else "https://news.ycombinator.com"

        reviews.append({
            "source": "Hacker News",
            "url": link,
            "date": date,
            "rating": "",
            "text": text,
        })
        if len(reviews) >= limit:
            break

    return reviews


def write_reviews(reviews, out_path, append=False):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    fieldnames = ["source", "url", "date", "rating", "text"]

    existing_urls = set()
    mode = "a" if append and os.path.isfile(out_path) else "w"

    if append and os.path.isfile(out_path):
        with open(out_path, mode="r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                u = row.get("url", "").strip()
                if u:
                    existing_urls.add(u)

    written = 0
    with open(out_path, mode=mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        for r in reviews:
            if r["url"] in existing_urls:
                continue
            writer.writerow(r)
            existing_urls.add(r["url"])
            written += 1

    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--app-id", help="Apple App Store numeric application ID")
    parser.add_argument("--hn-query", help="Hacker News query string for complaints or reviews")
    parser.add_argument("--limit", type=int, default=50, help="max items to fetch per source (default: 50)")
    parser.add_argument("--out", default="replica/reviews.csv", help="output CSV file path (default: replica/reviews.csv)")
    parser.add_argument("--append", action="store_true", help="append to existing CSV file")
    args = parser.parse_args(argv)

    if not args.app_id and not args.hn_query:
        print("fetch_reviews: specify at least one of --app-id or --hn-query", file=sys.stderr)
        return 2

    all_reviews = []
    if args.app_id:
        print(f"Fetching App Store reviews for ID {args.app_id}...")
        apple = fetch_apple_reviews(args.app_id, limit=args.limit)
        print(f"  found {len(apple)} App Store reviews")
        all_reviews.extend(apple)

    if args.hn_query:
        print(f"Searching Hacker News comments for '{args.hn_query}'...")
        hn = fetch_hn_discussions(args.hn_query, limit=args.limit)
        print(f"  found {len(hn)} Hacker News comments")
        all_reviews.extend(hn)

    count = write_reviews(all_reviews, args.out, append=args.append)
    print(f"Wrote {count} reviews to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
