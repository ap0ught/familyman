#!/usr/bin/env python3
"""
write_names_from_mapping.py
Read a mapping CSV (cluster_id,person_name) and the clusters.csv produced by
face_cluster_and_tag.py, then add the person_name as a Keyword to each image
using exiftool.

Requirements:
 - exiftool installed
Usage:
  python3 write_names_from_mapping.py --clusters clusters.csv --mapping my_mapping.csv --dry-run
"""
import csv
import argparse
import subprocess
import os
import sys

def read_mapping(path):
    m = {}
    with open(path, newline='', encoding='utf8') as fh:
        r = csv.reader(fh)
        for row in r:
            if not row: 
                continue
            if len(row) >= 2:
                key = row[0].strip()
                name = row[1].strip()
                if key:
                    m[int(key)] = name
    return m

def read_clusters(path):
    rows = []
    with open(path, newline='', encoding='utf8') as fh:
        r = csv.DictReader(fh)
        for row in r:
            try:
                rows.append((int(row['cluster_id']), row['filename']))
            except Exception:
                pass
    return rows

def run_exiftool_add_keyword(filename, keyword, dry_run=False):
    cmd = ["exiftool", "-overwrite_original", f"-Keywords+={keyword}", filename]
    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        return 0
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        print("exiftool error for", filename, proc.stderr.decode('utf8', errors='ignore'))
    return proc.returncode

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clusters", required=True, help="Path to clusters.csv")
    p.add_argument("--mapping", required=True, help="Path to mapping CSV: cluster_id,person_name")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    mapping = read_mapping(args.mapping)
    if not mapping:
        print("No mappings found. Mapping CSV should be 'cluster_id,person_name' per line.")
        sys.exit(1)
    clusters = read_clusters(args.clusters)
    for cid, fn in clusters:
        name = mapping.get(cid)
        if name:
            if not os.path.exists(fn):
                print("File not found:", fn)
                continue
            run_exiftool_add_keyword(fn, name, dry_run=args.dry_run)
    print("Done.")

if __name__ == "__main__":
    main()
