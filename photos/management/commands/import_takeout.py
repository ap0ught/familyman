import os
import json
import shutil
import zipfile
import tempfile
import hashlib
from django.core.management.base import BaseCommand
from photos.models import Photo
from datetime import datetime
from pathlib import Path

try:
    import face_recognition
except ImportError:
    face_recognition = None

class Command(BaseCommand):
    help = "Import a Google Takeout Google Photos folder into the database."

    def add_arguments(self, parser):
        parser.add_argument("takeout_root", help="Path to the root folder or zip file of the unpacked Google Takeout export")
        parser.add_argument("--dry-run", action="store_true", help="Don't write to DB; only report")
        parser.add_argument("--people-only", action="store_true", help="Only import photos with detected faces/people")
        parser.add_argument("--duplicate-action", choices=["skip", "replace", "error"], default="skip", 
                            help="How to handle duplicate photos (default: skip). 'skip' ignores duplicates, 'replace' updates existing records, 'error' stops on duplicates")
        parser.add_argument("--intake-dir", help="Directory for intake zip files (default: intake/)")
        parser.add_argument("--processed-dir", help="Directory for processed zip files (default: processed/)")
        parser.add_argument("--to-be-processed-dir", help="Directory for photos without people (default: to_be_processed/)")

    def calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of a file for duplicate detection."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.stderr.write(f"Error calculating hash for {file_path}: {e}")
            return None

    def has_faces(self, image_path):
        """Detect if an image has any faces/people in it."""
        try:
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(image, model='hog')
            return len(face_locations) > 0
        except Exception as e:
            self.stderr.write(f"Error detecting faces in {image_path}: {e}")
            self.stderr.write(f"Continuing with import - defaulting to including this photo")
            return True  # Default to True on error to avoid losing photos

    def handle(self, *args, **options):
        root = options["takeout_root"]
        dry = options["dry_run"]
        people_only = options["people_only"]
        duplicate_action = options["duplicate_action"]
        
        # Setup directories
        base_dir = Path.cwd()
        intake_dir = Path(options.get("intake_dir") or base_dir / "intake")
        processed_dir = Path(options.get("processed_dir") or base_dir / "processed")
        to_be_processed_dir = Path(options.get("to_be_processed_dir") or base_dir / "to_be_processed")
        
        # Create directories if they don't exist
        for directory in [intake_dir, processed_dir, to_be_processed_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Check if the input is a zip file
        is_zip = root.endswith('.zip') and os.path.isfile(root)
        temp_dir = None
        original_zip_path = None
        
        if is_zip:
            original_zip_path = root
            temp_dir = tempfile.mkdtemp(prefix="takeout_")
            self.stdout.write(f"Extracting {root} to {temp_dir}...")
            try:
                with zipfile.ZipFile(root, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                root = temp_dir
            except Exception as e:
                self.stderr.write(f"Failed to extract zip file: {e}")
                self.stderr.write(f"The zip file may be corrupted or incomplete.")
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return
        
        if not os.path.isdir(root):
            self.stderr.write("Path not found: " + root)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return
        
        if people_only and face_recognition is None:
            self.stderr.write("Error: --people-only requires face_recognition library.")
            self.stderr.write("Install with: pip install face_recognition")
            self.stderr.write("Note: face_recognition requires dlib and cmake. On Debian/Ubuntu:")
            self.stderr.write("  sudo apt-get install build-essential cmake python3-dev")
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return

        count = 0
        skipped_no_faces = 0
        skipped_duplicates = 0
        replaced_duplicates = 0
        import_successful = True
        try:
            for dirpath, _, filenames in os.walk(root):
                for fname in filenames:
                    base, ext = os.path.splitext(fname)
                    if ext.lower() in {".jpg", ".jpeg", ".png", ".heic", ".webp"}:
                        image_path = os.path.join(dirpath, fname)
                        
                        # Check for faces if people_only mode is enabled
                        has_people = True
                        if people_only:
                            has_people = self.has_faces(image_path)
                            if not has_people:
                                skipped_no_faces += 1
                                # Move to to_be_processed folder
                                if not dry:
                                    dest_path = to_be_processed_dir / fname
                                    # Handle duplicate filenames
                                    counter = 1
                                    while dest_path.exists():
                                        dest_path = to_be_processed_dir / f"{base}_{counter}{ext}"
                                        counter += 1
                                    shutil.copy2(image_path, dest_path)
                                    self.stdout.write(f"[NO FACES] Moved to to_be_processed: {fname}")
                                else:
                                    self.stdout.write(f"[DRY][NO FACES] Would move to to_be_processed: {fname}")
                                continue
                        
                        # Calculate file hash for duplicate detection
                        file_hash = self.calculate_file_hash(image_path)
                        if not file_hash:
                            self.stderr.write(f"Skipping {fname} due to hash calculation error")
                            continue
                        
                        # Check for duplicates in database
                        existing_photo = None
                        if file_hash:
                            existing_photo = Photo.objects.filter(file_hash=file_hash).first()
                        
                        if existing_photo:
                            if duplicate_action == "skip":
                                skipped_duplicates += 1
                                if dry:
                                    self.stdout.write(f"[DRY][DUPLICATE] Would skip: {fname} (already in DB as Photo {existing_photo.id})")
                                else:
                                    self.stdout.write(f"[DUPLICATE] Skipping: {fname} (already in DB as Photo {existing_photo.id})")
                                continue
                            elif duplicate_action == "error":
                                self.stderr.write(f"Error: Duplicate photo found: {fname} (already in DB as Photo {existing_photo.id})")
                                import_successful = False
                                break
                            # If replace, we'll update the existing photo below
                        
                        json_path = os.path.join(dirpath, base + ".json")
                        doc = {}
                        if os.path.exists(json_path):
                            try:
                                with open(json_path, "r", encoding="utf8") as fh:
                                    doc = json.load(fh)
                            except Exception as e:
                                self.stderr.write(f"Failed to parse JSON {json_path}: {e}")
                        title = doc.get("title") or doc.get("description") or ""
                        # photoTakenTime may be {"timestamp":"..."}
                        taken_at = None
                        pt = doc.get("photoTakenTime")
                        if isinstance(pt, dict):
                            ts = pt.get("timestamp")
                            try:
                                taken_at = datetime.utcfromtimestamp(int(ts))
                            except Exception:
                                taken_at = None
                        lat = None
                        lon = None
                        geo = doc.get("geoData") or doc.get("location")
                        if isinstance(geo, dict):
                            lat = geo.get("latitude") or geo.get("latitudeE7")
                            lon = geo.get("longitude") or geo.get("longitudeE7")
                            try:
                                if isinstance(lat, int) and abs(lat) > 1000:
                                    lat = lat / 1e7
                                if isinstance(lon, int) and abs(lon) > 1000:
                                    lon = lon / 1e7
                            except Exception:
                                pass
                        if dry:
                            if existing_photo and duplicate_action == "replace":
                                self.stdout.write(f"[DRY][REPLACE] Would update Photo {existing_photo.id}: {image_path}")
                                replaced_duplicates += 1
                            else:
                                self.stdout.write(f"[DRY] {image_path} taken_at={taken_at} lat={lat} lon={lon} hash={file_hash[:8]}...")
                                count += 1
                        else:
                            if existing_photo and duplicate_action == "replace":
                                # Update existing photo
                                existing_photo.original_path = image_path
                                existing_photo.title = title
                                existing_photo.description = doc.get("description") or ""
                                existing_photo.taken_at = taken_at
                                existing_photo.latitude = lat
                                existing_photo.longitude = lon
                                existing_photo.json_metadata = doc or None
                                existing_photo.save()
                                replaced_duplicates += 1
                                self.stdout.write(f"[REPLACE] Updated Photo {existing_photo.id}: {fname}")
                            else:
                                # Create new photo
                                photo = Photo.objects.create(
                                    original_path=image_path,
                                    file_hash=file_hash,
                                    title=title,
                                    description=doc.get("description") or "",
                                    taken_at=taken_at,
                                    latitude=lat,
                                    longitude=lon,
                                    json_metadata=doc or None,
                                )
                                count += 1
        except Exception as e:
            self.stderr.write(f"Error during import: {e}")
            import_successful = False
        
        # Clean up and move zip to processed folder if applicable
        if is_zip and original_zip_path:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            # Only move the zip if import was successful
            if import_successful and not dry:
                zip_filename = os.path.basename(original_zip_path)
                dest_zip_path = processed_dir / zip_filename
                # Handle duplicate filenames
                counter = 1
                while dest_zip_path.exists():
                    base_name, ext = os.path.splitext(zip_filename)
                    dest_zip_path = processed_dir / f"{base_name}_{counter}{ext}"
                    counter += 1
                shutil.move(original_zip_path, dest_zip_path)
                self.stdout.write(f"Moved zip to processed: {dest_zip_path}")
            elif dry:
                self.stdout.write(f"[DRY] Would move zip to processed folder")
            elif not import_successful:
                self.stdout.write(f"Import failed - zip file not moved: {original_zip_path}")
        
        if not dry:
            self.stdout.write(f"Imported {count} photos.")
            if replaced_duplicates > 0:
                self.stdout.write(f"Replaced {replaced_duplicates} duplicate photos.")
            if skipped_duplicates > 0:
                self.stdout.write(f"Skipped {skipped_duplicates} duplicate photos.")
            if people_only:
                self.stdout.write(f"Skipped {skipped_no_faces} photos without faces.")
        else:
            self.stdout.write(f"[DRY] Would import {count} photos.")
            if replaced_duplicates > 0:
                self.stdout.write(f"[DRY] Would replace {replaced_duplicates} duplicate photos.")
            if skipped_duplicates > 0:
                self.stdout.write(f"[DRY] Would skip {skipped_duplicates} duplicate photos.")
            if people_only:
                self.stdout.write(f"[DRY] Would skip {skipped_no_faces} photos without faces.")
