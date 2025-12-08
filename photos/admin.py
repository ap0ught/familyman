from django.contrib import admin
from .models import Photo, Person, Face

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name",)

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "taken_at")
    search_fields = ("title", "description", "original_path")

@admin.register(Face)
class FaceAdmin(admin.ModelAdmin):
    list_display = ("id", "photo", "person", "top", "left", "bottom", "right")
    list_filter = ("person",)
