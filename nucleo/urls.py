from django.urls import path,include
from .views.dashboardView import HomePage
from .views.pedidos_view import Pedido_view


urlpatterns= [
    path("home", HomePage.as_view(), name="home"),
    path('pedidos',Pedido_view.as_view(), name="pedidos" )
    
]

