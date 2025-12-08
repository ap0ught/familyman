# familyman Django site

Quickstart (local)

1. Create a virtualenv and install requirements:
   - python3 -m venv .venv
   - source .venv/bin/activate
   - pip install -r requirements.txt

2. Run migrations and create superuser:
   - python manage.py migrate
   - python manage.py createsuperuser

3. Run the dev server:
   - python manage.py runserver

4. Import a Google Takeout folder (dry-run first):
   - python manage.py import_takeout /path/to/unpacked_takeout --dry-run
   - Then run without --dry-run to import into the DB:
     - python manage.py import_takeout /path/to/unpacked_takeout

Notes
- This initial site stores original paths (it doesn't copy image files). To serve images via Django put or symlink your images under MEDIA_ROOT or adjust Photo model to use FileField and copy files into MEDIA_ROOT.
- The import command reads per-photo JSON sidecars produced by Google Takeout and stores JSON into the Photo.json_metadata field for later processing.

End of files.
