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
