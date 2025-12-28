# familyman

familyman is a small project to help you preserve family photos and related metadata exported from Google Photos (Google Takeout), and to recreate local "people" tags by clustering faces.

This repository contains helper scripts:
- merge_takeout_metadata.py — injects Takeout .json metadata (timestamps, descriptions, GPS, keywords) into image files using exiftool.
- face_cluster_and_tag.py — scans images, detects faces, computes embeddings, clusters similar faces, and writes a clusters.csv plus montage images for manual review.
- write_names_from_mapping.py — given a mapping from cluster_id -> person_name, writes the person name into images as a Keyword using exiftool.

## Django Photo Management App
The repository also includes a Django-based photo management application that provides a database for organizing and tracking imported photos.

### Import Takeout Command
The `import_takeout` management command imports Google Takeout photos into the Django database:

```bash
python manage.py import_takeout /path/to/takeout --dry-run
python manage.py import_takeout /path/to/takeout.zip
```

**People-Only Mode**: Import only photos with detected faces/people:
```bash
python manage.py import_takeout /path/to/takeout.zip --people-only
```

This mode uses face detection to filter photos:
- Photos with faces are imported into the database
- Photos without faces are moved to a `to_be_processed/` folder for later review
- Processed zip files are moved to a `processed/` folder

**Duplicate Handling**: Control what happens when duplicate photos are detected (based on file content hash):
```bash
# Skip duplicates (default behavior)
python manage.py import_takeout /path/to/takeout.zip --duplicate-action skip

# Replace existing photos with new metadata
python manage.py import_takeout /path/to/takeout.zip --duplicate-action replace

# Stop with error on duplicates
python manage.py import_takeout /path/to/takeout.zip --duplicate-action error
```

**Options**:
- `--dry-run` — Preview what would be imported without making changes
- `--people-only` — Only import photos with detected faces
- `--duplicate-action` — How to handle duplicates: `skip` (default), `replace`, or `error`
- `--intake-dir` — Directory for intake zip files (default: `intake/`)
- `--processed-dir` — Directory for processed zip files (default: `processed/`)
- `--to-be-processed-dir` — Directory for photos without people (default: `to_be_processed/`)

### Cleanup Duplicates Command
Remove duplicate photos that are already in the database:

```bash
# IMPORTANT: For existing installations, first compute hashes for photos that don't have them
python manage.py cleanup_duplicates --compute-hashes

# Report duplicates without deleting
python manage.py cleanup_duplicates --action report

# Delete duplicates, keeping the oldest copy
python manage.py cleanup_duplicates --action delete

# Dry run to see what would be deleted
python manage.py cleanup_duplicates --action delete --dry-run
```

**Note**: For existing installations with photos imported before the duplicate detection feature, you must run `--compute-hashes` first to calculate hashes for existing photos. After that, you can use `--action report` to see duplicates or `--action delete` to remove them.

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

## Running on Raspberry Pi
For detailed instructions on running familyman on a Raspberry Pi (aarch64/ARM), see [README-pi.md](README-pi.md). A setup script is provided to automate the installation process:
```bash
./setup_pi.sh
```

Notes and limitations
- Google does not export its internal face-recognition groupings or face embeddings in Takeout. These scripts attempt to recreate a local people index by detecting faces and clustering them using open-source models.
- Clustering will not be perfect; manual review of cluster montages is recommended before writing names.
- Videos are not fully handled by these scripts (still images only). You can extract thumbnails if you want to include video frames.

License
This project is released under the MIT license. See LICENSE.
