#!/usr/bin/env bash
set -euo pipefail

# Usage:
# 1) Clone the empty repo: git clone https://github.com/ap0ught/familyman.git
# 2) cd familyman
# 3) Save this script as create_and_push.sh and run:
#    chmod +x create_and_push.sh
#    ./create_and_push.sh
#
# The script creates the initial files, commits, and pushes to origin/main.

echo "Creating files for familyman..."

cat > merge_takeout_metadata.py <<'PY'
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
PY

cat > face_cluster_and_tag.py <<'PY'
#!/usr/bin/env python3
"""
face_cluster_and_tag.py
Scan a folder of images, detect faces, compute face embeddings and cluster them.
Output:
 - clusters.csv : cluster_id, filename, face_index_in_image
 - cluster_<id>.jpg : small montage of faces in that cluster for quick inspection

Requirements:
 - Python 3.8+
 - pip install face_recognition scikit-learn Pillow numpy
Usage:
  python3 face_cluster_and_tag.py /path/to/images --out outdir
After you inspect the clusters and create a CSV mapping cluster_id -> person_name,
you can optionally run the included write-names step to add the person_name as a Keyword to each image
using exiftool.
"""
import os
import sys
import argparse
import csv
from PIL import Image
import numpy as np

try:
    import face_recognition
    from sklearn.cluster import DBSCAN
except Exception:
    print("Missing dependencies. Please install: pip install face_recognition scikit-learn Pillow numpy")
    sys.exit(1)

def find_images(root, exts={'.jpg', '.jpeg', '.png', '.heic', '.webp'}):
    out = []
    for dp, _, files in os.walk(root):
        for f in files:
            if os.path.splitext(f)[1].lower() in exts:
                out.append(os.path.join(dp, f))
    return out

def make_montage(images, thumb_size=(128,128), cols=10):
    if not images:
        return None
    rows = (len(images) + cols - 1) // cols
    w, h = thumb_size
    montage = Image.new('RGB', (cols*w, rows*h), (30,30,30))
    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        img = img.resize(thumb_size, Image.LANCZOS)
        montage.paste(img, (c*w, r*h))
    return montage

def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="root folder with images")
    p.add_argument("--out", default="face_clusters_out", help="output folder")
    p.add_argument("--model", choices=['hog','cnn'], default='hog', help="face detection model")
    p.add_argument("--eps", type=float, default=0.5, help="DBSCAN eps")
    p.add_argument("--min-samples", type=int, default=2, help="DBSCAN min_samples")
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    images = find_images(args.root)
    print(f"Found {len(images)} images — scanning for faces (this may take a while).")
    encs = []
    meta = []  # (filename, face_location)
    for fn in images:
        try:
            img = face_recognition.load_image_file(fn)
            locs = face_recognition.face_locations(img, model=args.model)
            if not locs:
                continue
            feats = face_recognition.face_encodings(img, locs)
            for i, e in enumerate(feats):
                encs.append(e)
                meta.append((fn, locs[i]))
        except Exception as e:
            print("Error processing", fn, e)
    if not encs:
        print("No faces found.")
        return
    X = np.vstack(encs)
    clustering = DBSCAN(eps=args.eps, min_samples=args.min_samples, metric='euclidean').fit(X)
    labels = clustering.labels_
    # Save CSV
    csv_path = os.path.join(args.out, "clusters.csv")
    with open(csv_path, "w", newline='', encoding='utf8') as fh:
        w = csv.writer(fh)
        w.writerow(["cluster_id", "filename", "face_index", "top", "right", "bottom", "left"])
        for i, lab in enumerate(labels):
            fn, (top, right, bottom, left) = meta[i]
            w.writerow([int(lab), fn, i, top, right, bottom, left])
    print("Wrote", csv_path)
    # Create montages per cluster
    clusters = {}
    for i, lab in enumerate(labels):
        clusters.setdefault(int(lab), []).append(i)
    for lab, indices in clusters.items():
        faces_images = []
        for idx in indices:
            fn, (top, right, bottom, left) = meta[idx]
            try:
                img = Image.open(fn).convert('RGB')
                face = img.crop((left, top, right, bottom)).resize((128,128), Image.LANCZOS)
                faces_images.append(face)
            except Exception:
                pass
        montage = make_montage(faces_images, thumb_size=(128,128), cols=8)
        if montage:
            outfn = os.path.join(args.out, f"cluster_{lab}.jpg")
            montage.save(outfn, quality=85)
    print(f"Created {len(clusters)} cluster montages in {args.out}")
    print("Open clusters.csv and the cluster_*.jpg files to inspect clusters. Assign names externally and then you can write keywords into images with exiftool if desired.")

if __name__ == "__main__":
    main()
PY

cat > write_names_from_mapping.py <<'PY'
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
PY

cat > README.md <<'MD'
# familyman

familyman is a small project to help you preserve family photos and related metadata exported from Google Photos (Google Takeout), and to recreate local "people" tags by clustering faces.

This repository contains helper scripts:
- merge_takeout_metadata.py — injects Takeout .json metadata (timestamps, descriptions, GPS, keywords) into image files using exiftool.
- face_cluster_and_tag.py — scans images, detects faces, computes embeddings, clusters similar faces, and writes a clusters.csv plus montage images for manual review.
- write_names_from_mapping.py — given a mapping from cluster_id -> person_name, writes the person name into images as a Keyword using exiftool.

Overview workflow:
1. Create a Google Photos export using Google Takeout and download/unpack it.
2. Run merge_takeout_metadata.py to re-embed timestamp/location/description/keywords into the image files:
   - Dry-run first: python3 merge_takeout_metadata.py /path/to/takeout --dry-run
   - Then run for real.
3. Run face_cluster_and_tag.py to detect and cluster faces. Inspect the produced `face_clusters_out/clusters.csv` and `cluster_*.jpg` montages.
4. Create a mapping CSV (cluster_id,person_name) for clusters you want to name.
5. Run write_names_from_mapping.py to write the names as Keywords into photos:
   - python3 write_names_from_mapping.py --clusters face_clusters_out/clusters.csv --mapping my_mapping.csv

Prerequisites
- exiftool (https://exiftool.org/) on PATH
- Python 3.8+
- For face clustering:
  - pip install face_recognition scikit-learn Pillow numpy
  - face_recognition requires dlib; follow installation instructions for your OS.

Notes and limitations
- Google does not export its internal face-recognition groupings or face embeddings in Takeout. These scripts attempt to recreate a local people index by detecting faces and clustering them using open-source models.
- Clustering will not be perfect; manual review of cluster montages is recommended before writing names.
- Videos are not fully handled by these scripts (still images only). You can extract thumbnails if you want to include video frames.

License
This project is released under the MIT license. See LICENSE.
MD

cat > .gitignore <<'GI'
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Environment
.env
.venv/
venv/

# macOS
.DS_Store

# ExifTool backup files
*_original
GI

cat > LICENSE <<'LIC'
MIT License

Copyright (c) 2025 ap0ught

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
LIC

chmod +x merge_takeout_metadata.py face_cluster_and_tag.py write_names_from_mapping.py

# Git commit and push
git add .
git commit -m "Initial commit: add scripts and README"
# Ensure branch main
git branch -M main || true
git push -u origin main

echo "Done. Files created, committed, and pushed to origin/main."
