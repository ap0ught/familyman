import os
import json
from django.core.management.base import BaseCommand
from photos.models import Photo
from datetime import datetime

class Command(BaseCommand):
    help = "Import a Google Takeout Google Photos folder into the database."

    def add_arguments(self, parser):
        parser.add_argument("takeout_root", help="Path to the root folder of the unpacked Google Takeout export")
        parser.add_argument("--dry-run", action="store_true", help="Don't write to DB; only report")

    def handle(self, *args, **options):
        root = options["takeout_root"]
        dry = options["dry_run"]
        if not os.path.isdir(root):
            self.stderr.write("Path not found: " + root)
            return

        count = 0
        for dirpath, _, filenames in os.walk(root):
            for fname in filenames:
                base, ext = os.path.splitext(fname)
                if ext.lower() in {".jpg", ".jpeg", ".png", ".heic", ".webp"}:
                    image_path = os.path.join(dirpath, fname)
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
                        self.stdout.write(f"[DRY] {image_path} taken_at={taken_at} lat={lat} lon={lon}")
                    else:
                        photo = Photo.objects.create(
                            original_path=image_path,
                            title=title,
                            description=doc.get("description") or "",
                            taken_at=taken_at,
                            latitude=lat,
                            longitude=lon,
                            json_metadata=doc or None,
                        )
                        count += 1
        if not dry:
            self.stdout.write(f"Imported {count} photos.")
