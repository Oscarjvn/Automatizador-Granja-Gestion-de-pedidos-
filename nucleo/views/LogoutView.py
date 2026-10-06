from django.contrib.auth.views import LogoutView
from django.urls import reverse_lazy

class LogoutView(LogoutView):
    # Almacena a dónde va el usuario tras cerrar sesión
    next_page = reverse_lazy('home')  # O simplemente '/'
