from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import DetailView, TemplateView, ListView
from django.core.paginator import Paginator
from nucleo.mixin import TiendaRequeridaMixin
from nucleo.models import Pedido, Producto
from nucleo.services.pedidos import generar_pedido_sugerido
from nucleo.services.reposicion import productos_a_reponer


class ReposicionView(TiendaRequeridaMixin, TemplateView):
    template_name = 'reposicion.html'
    paginate_by= 10

    

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        productos_reposicion = productos_a_reponer(tienda=self.tienda)
        paginator= Paginator(productos_reposicion, self.paginate_by)
        print(type(paginator), paginator)
        page_obj= paginator.get_page(self.request.GET.get('page'))

        ctx['page_obj'] = page_obj
        ctx['candidatos'] = page_obj.object_list
        ctx['is_paginated'] = page_obj.has_other_pages()
        return ctx
   

    def post(self, request, *args, **kwargs):
        items = self._parse_items(request.POST)
        pedido = generar_pedido_sugerido(self.tienda, request.user, items)

        if pedido:
            messages.success(request, f"Pedido #{pedido.pk} creado exitosamente.")
            return redirect('pedido_detalle', pk=pedido.pk)

        messages.warning(request, "No se seleccionó ningún producto.")
        return redirect('reposicion')

    def _parse_items(self, post_data):
        """
        Extrae los items del POST.

        Formato esperado:
            sugerido_<sku> = valor del sistema (oculto)
            ajustada_<sku> = valor del usuario (editable)

        Retorna: [{'producto', 'cant_sugerida', 'cant_ajustada'}, ...]
        """
        items = []
        for key in post_data:
            if not key.startswith('ajustada_'):
                continue

            sku = key.replace('ajustada_', '')

            try:
                cant_ajustada = int(post_data[key])
                cant_sugerida = int(post_data.get(f'sugerido_{sku}', cant_ajustada))
            except (ValueError, TypeError):
                continue

            # Si el usuario pone 0 o negativo, se omite del pedido
            if cant_ajustada <= 0:
                continue

            try:
                producto = Producto.objects.get(sku=sku)
            except Producto.DoesNotExist:
                continue

            items.append({
                'producto': producto,
                'cant_sugerida': cant_sugerida,
                # Solo se guarda cant_ajustada si difiere del sugerido
                'cant_ajustada': cant_ajustada if cant_ajustada != cant_sugerida else None,
            })

        return items