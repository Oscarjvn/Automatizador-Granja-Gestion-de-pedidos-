from django.db import models

from nucleo.tenant import get_tienda_actual


class TenantQuerySet(models.QuerySet):

    def de_tienda(self, tienda):
        return self.filter(tienda=tienda)

    def sin_filtro(self):
        return self


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Filtra automáticamente por la tienda activa del contexto.
    Sin tienda activa → queryset vacío (seguro por defecto).
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tienda = get_tienda_actual()
        if tienda is None:
            return qs.none()
        return qs.filter(tienda=tienda)