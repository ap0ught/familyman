"""Utilities for calculating file hashes."""
import hashlib


def calculate_file_hash(file_path):
    """Calculate SHA256 hash of a file for duplicate detection.
    
    Args:
        file_path: Path to the file to hash
        
    Returns:
        The SHA256 hex digest string, or None if an error occurs
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except (IOError, OSError, PermissionError):
        # Expected errors when reading files (missing, permission denied, etc.)
        return None
