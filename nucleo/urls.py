from django.urls import path,include
from .views.dashboardView import HomePage
from .views.pedidos_view import Pedido_view
from .views.reposicion_view import ReposicionView
from .views.pedido_detalle_view import PedidoDetalleView
from .views.vistas_transicion_estados_pedidos import PedidoAprobarView
from .views.vistas_transicion_estados_pedidos import PedidoCancelarView
from .views.vistas_transicion_estados_pedidos import PedidoRecibirView



urlpatterns= [
    path("home", HomePage.as_view(), name="home"),
    path('pedidos',Pedido_view.as_view(), name="pedidos" ),
    path('reposicion/', ReposicionView.as_view(), name='reposicion'),
    path('pedidos/<int:pk>/', PedidoDetalleView.as_view(), name='pedido_detalle'),
    path('pedidos/<int:pk>/aprobar/', PedidoAprobarView.as_view(), name='pedido_aprobar'),
    path('pedidos/<int:pk>/cancelar/', PedidoCancelarView.as_view(), name='pedido_cancelar'),
    path('pedidos/<int:pk>/recibir/', PedidoRecibirView.as_view(), name='pedido_recibir'),
    
]

