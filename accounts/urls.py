from django.urls import path
from . import views

urlpatterns= [
    path("singup/", views.SingupView.as_view(), name="singup")
]