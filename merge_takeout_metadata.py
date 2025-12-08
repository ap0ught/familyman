#!/usr/bin/env python3
"""
merge_takeout_metadata.py
Given a root folder from Google Takeout (Google Photos), find image files and their
corresponding .json sidecars and inject common metadata (DateTimeOriginal,
Description/Caption, GPS) into the image files using exiftool.

Requirements:
 - exiftool must be installed and on PATH (https://exiftool.org/)
 - Python 3.7+
Usage:
  python3 merge_takeout_metadata.py /path/to/takeout_root --dry-run
"""
import os
import sys
import json
import argparse
import subprocess
from datetime import datetime

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.heic', '.mp4', '.mov', '.gif', '.webp'}

def iso_from_timestamp(ts):
    try:
        t = int(ts)
        dt = datetime.utcfromtimestamp(t)
        return dt.strftime("%Y:%m:%d %H:%M:%S")
    except Exception:
        return None

def build_exiftool_args(jsondata):
    args = []
    # Date/time
    pt = jsondata.get('photoTakenTime') or jsondata.get('photoTakenTime')
    if isinstance(pt, dict):
        ts = pt.get('timestamp') or pt.get('timestamp')
        dt = iso_from_timestamp(ts)
        if dt:
            args += [f"-DateTimeOriginal={dt}", f"-CreateDate={dt}", f"-ModifyDate={dt}"]
    # Description / caption
    desc = jsondata.get('description') or jsondata.get('title') or jsondata.get('caption')
    if desc:
        args += [f"-Caption-Abstract={desc}", f"-ImageDescription={desc}", f"-Description={desc}"]
    # Keywords / tags
    kw = jsondata.get('labels') or jsondata.get('keywords') or jsondata.get('photoTags')
    if isinstance(kw, list) and kw:
        for k in kw:
            args.append(f"-Keywords={k}")
    # Location
    geo = jsondata.get('geoData') or jsondata.get('location')
    if isinstance(geo, dict):
        lat = geo.get('latitude') or geo.get('latitudeE7')
        lon = geo.get('longitude') or geo.get('longitudeE7')
        try:
            if isinstance(lat, int) and abs(lat) > 1000:
                lat = lat / 1e7
            if isinstance(lon, int) and abs(lon) > 1000:
                lon = lon / 1e7
        except Exception:
            pass
        if lat and lon:
            args += [f"-GPSLatitude={lat}", f"-GPSLongitude={lon}", "-GPSLatitudeRef=N", "-GPSLongitudeRef=E"]
    return args

def run_exiftool(args, target, dry_run=False):
    cmd = ["exiftool", "-overwrite_original"]
    cmd.extend(args)
    cmd.append(target)
    if dry_run:
        print("DRY-RUN:", " ".join(cmd))
        return 0
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        print("exiftool error:", proc.stderr.decode('utf8', errors='ignore'))
    return proc.returncode

def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Path to unpacked Google Takeout root (Google Photos)")
    p.add_argument("--dry-run", action="store_true", help="Show commands without running exiftool")
    args = p.parse_args()

    root = args.root
    if not os.path.isdir(root):
        print("root path not found:", root)
        sys.exit(1)

    count = 0
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            base, ext = os.path.splitext(f)
            if ext.lower() in IMAGE_EXTS:
                image_path = os.path.join(dirpath, f)
                json_path = os.path.join(dirpath, base + ".json")
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r", encoding="utf8") as fh:
                            jd = json.load(fh)
                    except Exception as e:
                        print("Failed to parse JSON:", json_path, e)
                        continue
                    exif_args = build_exiftool_args(jd)
                    if exif_args:
                        ret = run_exiftool(exif_args, image_path, dry_run=args.dry_run)
                        if ret == 0:
                            count += 1
    print(f"Processed {count} files (metadata injected where found).")

if __name__ == "__main__":
    main()
