from django.contrib import admin
from django.db import models
from .models import Photo, Person, Face

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("name", "photo_count")
    search_fields = ("name", "notes")
    list_per_page = 50
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _photo_count=models.Count("faces__photo", distinct=True)
        )
        return queryset
    
    @admin.display(description="Photos", ordering="_photo_count")
    def photo_count(self, obj):
        return obj._photo_count

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "taken_at", "location", "face_count")
    search_fields = ("title", "description", "original_path")
    list_filter = ("taken_at",)
    date_hierarchy = "taken_at"
    list_per_page = 50
    readonly_fields = ("created_at", "location_display")
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("title", "description", "original_path")
        }),
        ("Metadata", {
            "fields": ("taken_at", "latitude", "longitude", "location_display", "json_metadata"),
            "classes": ("collapse",)
        }),
        ("System", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _face_count=models.Count("faces")
        )
        return queryset
    
    @admin.display(description="Location")
    def location(self, obj):
        if obj.latitude and obj.longitude:
            return f"{obj.latitude:.4f}, {obj.longitude:.4f}"
        return "-"
    
    @admin.display(description="Faces", ordering="_face_count")
    def face_count(self, obj):
        return obj._face_count
    
    @admin.display(description="Location Details")
    def location_display(self, obj):
        if obj.latitude and obj.longitude:
            return f"Latitude: {obj.latitude}, Longitude: {obj.longitude}"
        return "No location data"

@admin.register(Face)
class FaceAdmin(admin.ModelAdmin):
    list_display = ("id", "photo_link", "person", "bounding_box", "has_embedding")
    list_filter = ("person",)
    search_fields = ("photo__title", "person__name")
    list_per_page = 50
    autocomplete_fields = ["person", "photo"]
    
    @admin.display(description="Photo", ordering="photo")
    def photo_link(self, obj):
        return f"Photo {obj.photo.id}: {obj.photo.title or 'Untitled'}"
    
    @admin.display(description="Bounding Box")
    def bounding_box(self, obj):
        return f"({obj.top}, {obj.left}) → ({obj.bottom}, {obj.right})"
    
    @admin.display(description="Has Embedding", boolean=True)
    def has_embedding(self, obj):
        return bool(obj.embedding)
