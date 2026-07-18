from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import CustomUserCreationForm
# Create your views here.

class SingupView(CreateView):
    form_class= CustomUserCreationForm
    success_url= reverse_lazy("login")
    template_name= "singup.html"

