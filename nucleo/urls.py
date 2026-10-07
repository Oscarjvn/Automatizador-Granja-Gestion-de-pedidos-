from django.urls import path,include
from .views.dashboardView import HomePage
from .views.pedidos_view import Pedido_view
from .views.reposicion_view import ReposicionView
from .views.pedido_detalle_view import PedidoDetalleView
from .views.vistas_transicion_estados_pedidos import PedidoAprobarView
from .views.vistas_transicion_estados_pedidos import PedidoCancelarView
from .views.vistas_transicion_estados_pedidos import PedidoRecibirView
from .views.inventario_view import InventarioView
from .views.vencimientos_view import VencimientosView
from .views.reportes.dashboard_view import DashboardReportesView
from .views.reportes.historico_view import HistoricoView
from .views.reportes.rotacion_view import RotacionView
from .views.reportes.comparativa_view import ComparativaView
from .views.LogoutView import LogoutView
from django.contrib.auth import views as auth_views
from .views.exportar_view import ExportarPedidoView, ExportarListaPedidosView
from .views.prediccion_view import PrediccionView



urlpatterns= [
    path("home", HomePage.as_view(), name="home"),
    path('pedidos',Pedido_view.as_view(), name="pedidos" ),
    path('reposicion/', ReposicionView.as_view(), name='reposicion'),
    path('pedidos/<int:pk>/', PedidoDetalleView.as_view(), name='pedido_detalle'),
    path('pedidos/<int:pk>/aprobar/', PedidoAprobarView.as_view(), name='pedido_aprobar'),
    path('pedidos/<int:pk>/cancelar/', PedidoCancelarView.as_view(), name='pedido_cancelar'),
    path('pedidos/<int:pk>/recibir/', PedidoRecibirView.as_view(), name='pedido_recibir'),
    path('inventario/', InventarioView.as_view(), name='inventario'),
    #rutas de analisis de ventas
    path('reportes/', DashboardReportesView.as_view(), name='reportes'),
    path('reportes/historico/', HistoricoView.as_view(), name='reportes_historico'),
    path('reportes/rotacion/', RotacionView.as_view(), name='reportes_rotacion'),
    path('reportes/comparativa/', ComparativaView.as_view(), name='reportes_comparativa'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password-reset/',
         auth_views.PasswordResetView.as_view(),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('reset/done/',
         auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
     # Exportaciones
    path('pedidos/<int:pk>/exportar/', ExportarPedidoView.as_view(), name='exportar_pedido'),
    path('pedidos/exportar/', ExportarListaPedidosView.as_view(), name='exportar_lista_pedidos'),
    path('vencimientos/', VencimientosView.as_view(), name='vencimientos'),
    path('reportes/prediccion/', PrediccionView.as_view(), name='reportes_prediccion'),
    
]

