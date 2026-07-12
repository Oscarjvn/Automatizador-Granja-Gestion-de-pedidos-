from django.shortcuts import render
from django.views.generic import TemplateView
from ..models import Pedido, InventarioProducto, Lote,Tienda
from django.utils import timezone 
from datetime import timedelta

# Create your views here.

class HomePage(TemplateView):
    template_name= "home.html"
    def get_context_data(self, **kwargs):
        context= super().get_context_data(**kwargs)
        hoy= timezone.now()
        dos_meses= hoy + timedelta(days=60)
        context["pedidos"]= Pedido.objects.filter(estatus= "Borrador")
        context["inventario"]= InventarioProducto.objects.all()[:30]#aqui obtengo los primeros diez productos del inventario
        context["vencimiento"]=Lote.objects.filter(fecha_vencimiento__range=[hoy, dos_meses]).order_by("fecha_vencimiento")#esto es para filtrar por fecha de vencimiento
        context["tienda"]= Tienda.objects.all()
        print(context)
    
        return context
