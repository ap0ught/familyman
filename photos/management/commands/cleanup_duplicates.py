import hashlib
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from photos.models import Photo


class Command(BaseCommand):
    help = "Find and remove duplicate photos from the database based on file content hash."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Don't delete anything; only report duplicates")
        parser.add_argument("--action", choices=["delete", "report"], default="report",
                            help="Action to take on duplicates. 'report' only shows duplicates (default), 'delete' removes them keeping the oldest")
        parser.add_argument("--compute-hashes", action="store_true", 
                            help="Compute hashes for photos that don't have them yet")

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

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        action = options["action"]
        compute_hashes = options["compute_hashes"]

        # First, compute hashes for photos that don't have them
        if compute_hashes:
            photos_without_hash = Photo.objects.filter(Q(file_hash='') | Q(file_hash__isnull=True))
            count_without_hash = photos_without_hash.count()
            
            if count_without_hash > 0:
                self.stdout.write(f"Computing hashes for {count_without_hash} photos without hash...")
                computed = 0
                failed = 0
                
                for photo in photos_without_hash:
                    file_hash = self.calculate_file_hash(photo.original_path)
                    if file_hash:
                        if not dry_run:
                            photo.file_hash = file_hash
                            photo.save(update_fields=['file_hash'])
                        computed += 1
                        if computed % 100 == 0:
                            self.stdout.write(f"  Processed {computed}/{count_without_hash}...")
                    else:
                        failed += 1
                
                if dry_run:
                    self.stdout.write(f"[DRY] Would compute hashes for {computed} photos ({failed} failed)")
                else:
                    self.stdout.write(f"Computed hashes for {computed} photos ({failed} failed)")
            else:
                self.stdout.write("All photos already have hashes.")

        # Find duplicates by file_hash
        self.stdout.write("\nLooking for duplicate photos...")
        
        # Get all file_hashes that appear more than once
        duplicate_hashes = (Photo.objects
                           .values('file_hash')
                           .annotate(count=Count('id'))
                           .filter(count__gt=1, file_hash__isnull=False)
                           .exclude(file_hash="")
                           .order_by('-count'))

        if not duplicate_hashes:
            self.stdout.write("No duplicates found!")
            return

        total_duplicates = sum(h['count'] - 1 for h in duplicate_hashes)
        self.stdout.write(f"Found {len(duplicate_hashes)} sets of duplicates ({total_duplicates} duplicate photos total)")

        if action == "report" or dry_run:
            # Just report the duplicates
            for dup in duplicate_hashes:
                file_hash = dup['file_hash']
                count = dup['count']
                photos = Photo.objects.filter(file_hash=file_hash).order_by('created_at')
                
                self.stdout.write(f"\n  Hash {file_hash[:16]}... has {count} copies:")
                for i, photo in enumerate(photos):
                    marker = "[KEEP]" if i == 0 else "[DELETE]"
                    self.stdout.write(f"    {marker} Photo {photo.id}: {photo.original_path} (created: {photo.created_at})")

        if action == "delete" and not dry_run:
            # Delete duplicates, keeping the oldest (first created)
            deleted_count = 0
            for dup in duplicate_hashes:
                file_hash = dup['file_hash']
                photos = Photo.objects.filter(file_hash=file_hash).order_by('created_at')
                
                # Keep the first (oldest), delete the rest
                to_delete = list(photos[1:])
                for photo in to_delete:
                    self.stdout.write(f"  Deleting Photo {photo.id}: {photo.original_path}")
                    photo.delete()
                    deleted_count += 1
            
            self.stdout.write(f"\nDeleted {deleted_count} duplicate photos.")
        elif action == "delete" and dry_run:
            self.stdout.write(f"\n[DRY] Would delete {total_duplicates} duplicate photos.")
