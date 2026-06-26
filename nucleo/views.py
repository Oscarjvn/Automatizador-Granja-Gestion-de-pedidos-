from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, JsonResponse, Http404
from django.views.generic import TemplateView
from .models import Pedido
# Create your views here.
class HomePage(TemplateView):
    template_name= "home.html"
    def get_context_data(self, **kwargs):
        context= super().get_context_data(**kwargs)
        context["pedidos"]= Pedido.objects.filter(estatus= "pendiete")
        return context
