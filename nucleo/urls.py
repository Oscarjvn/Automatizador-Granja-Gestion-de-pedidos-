from django.urls import path
from .views.dashboardView import HomePage

urlpatterns= [
    path("", HomePage.as_view(), name="home")
]

