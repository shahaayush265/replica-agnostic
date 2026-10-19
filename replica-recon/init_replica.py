#!/usr/bin/env python3
"""Initialize the replica workspace directory and templates. Standard library only.

Creates the standard replica/ directory layout and populates starter templates
from the skill pack if they do not already exist:

    python3 init_replica.py
    python3 init_replica.py --app-name "MyClone" --target replica

Creates:
    replica/
    replica/recon.md
    replica/features.csv
    replica/screens/
    replica/clone-screens/
    replica/diffs/
    replica/design/tokens.json
    replica/launch/listing.json
"""

import argparse
import os
import shutil
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


def find_template(rel_path):
    candidates = [
        os.path.join(PACK_ROOT, "skills", rel_path),
        os.path.join(PACK_ROOT, rel_path),
        os.path.join(SCRIPT_DIR, "..", rel_path.split("/")[-1]),
        os.path.join(SCRIPT_DIR, "..", "resources", rel_path.split("/")[-1]),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def init_workspace(target_dir="replica", app_name=None, force=False):
    os.makedirs(target_dir, exist_ok=True)
    subdirs = ["screens", "clone-screens", "diffs", "design", "launch"]
    for sub in subdirs:
        os.makedirs(os.path.join(target_dir, sub), exist_ok=True)

    templates = [
        ("replica-recon/recon-map.md", os.path.join(target_dir, "recon.md")),
        ("replica-recon/features.csv", os.path.join(target_dir, "features.csv")),
        ("replica-design/tokens.json", os.path.join(target_dir, "design", "tokens.json")),
        ("replica-launch/listing.example.json", os.path.join(target_dir, "launch", "listing.json")),
    ]

    copied = []
    skipped = []

    for src_rel, dest_path in templates:
        if os.path.isfile(dest_path) and not force:
            skipped.append(dest_path)
            continue
        src = find_template(src_rel)
        if src and os.path.isfile(src):
            with open(src, "r", encoding="utf-8") as sf:
                content = sf.read()
            if app_name and dest_path.endswith(".md"):
                content = content.replace("Target App", app_name)
            with open(dest_path, "w", encoding="utf-8") as df:
                df.write(content)
            copied.append(dest_path)
        else:
            # Fallback starter content if template not found
            if dest_path.endswith("features.csv"):
                with open(dest_path, "w", encoding="utf-8") as df:
                    df.write("feature,area,priority,original,clone,notes\n")
                copied.append(dest_path)

    return copied, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--target", default="replica", help="target directory (default: replica)")
    parser.add_argument("--app-name", help="optional app name to customize templates")
    parser.add_argument("--force", action="store_true", help="overwrite existing template files")
    args = parser.parse_args(argv)

    copied, skipped = init_workspace(target_dir=args.target, app_name=args.app_name, force=args.force)

    print("Initialized replica workspace at '%s/'" % args.target)
    for c in copied:
        print("  created: %s" % c)
    for s in skipped:
        print("  kept (already exists): %s" % s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
