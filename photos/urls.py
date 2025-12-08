from django.urls import path
from . import views

app_name = "photos"

urlpatterns = [
    path("", views.PhotoListView.as_view(), name="index"),
    path("photo/<int:pk>/", views.PhotoDetailView.as_view(), name="photo_detail"),
    path("api/photos/", views.PhotoListAPI.as_view(), name="api_photos"),
]
