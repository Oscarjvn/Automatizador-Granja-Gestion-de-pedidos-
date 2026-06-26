from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
# Create your views here.
def home_page(request):
    return HttpResponse("Granja pedidos")