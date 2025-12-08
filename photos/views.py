from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Photo
from django.forms.models import model_to_dict

class PhotoListView(ListView):
    model = Photo
    template_name = "photos/photo_list.html"
    context_object_name = "photos"
    paginate_by = 50

class PhotoDetailView(DetailView):
    model = Photo
    template_name = "photos/photo_detail.html"
    context_object_name = "photo"

class PhotoListAPI(APIView):
    def get(self, request):
        qs = Photo.objects.order_by("-taken_at")[:200]
        data = [model_to_dict(p, fields=["id", "title", "original_path", "taken_at"]) for p in qs]
        return Response(data)
