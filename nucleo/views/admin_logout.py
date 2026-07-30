from django.contrib.auth import logout
from django.shortcuts import redirect

def custom_admin_logout(request):
    """
    Vista personalizada para que Jazzmin y los enlaces GET 
    puedan cerrar sesión en Django 5+ sin dar error 405.
    """
    logout(request)
    return redirect('login')  # O redirige a 'admin:login' si prefieres el login del admin