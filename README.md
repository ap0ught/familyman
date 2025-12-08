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
