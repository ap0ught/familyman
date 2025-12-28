from django.db import models

class Person(models.Model):
    name = models.CharField(max_length=200, unique=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Photo(models.Model):
    # Store path to the original file (relative or absolute). Optionally you can copy into MEDIA_ROOT.
    original_path = models.TextField(help_text="Path to the image file on disk")
    file_hash = models.CharField(max_length=64, blank=True, db_index=True, help_text="SHA256 hash of file content for duplicate detection")
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    json_metadata = models.JSONField(null=True, blank=True)
    people = models.ManyToManyField(Person, through="Face", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo {self.id}: {self.title or self.original_path}"

class Face(models.Model):
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="faces")
    person = models.ForeignKey(Person, on_delete=models.SET_NULL, null=True, blank=True, related_name="faces")
    # bounding box in pixels (top, right, bottom, left) as integers
    top = models.IntegerField()
    right = models.IntegerField()
    bottom = models.IntegerField()
    left = models.IntegerField()
    embedding = models.BinaryField(null=True, blank=True, help_text="Serialized face embedding (optional)")

    def __str__(self):
        return f"Face {self.id} in Photo {self.photo_id} -> {self.person or 'unknown'}"
