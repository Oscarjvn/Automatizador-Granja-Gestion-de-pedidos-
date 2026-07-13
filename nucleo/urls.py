from django.urls import path,include
from .views.dashboardView import HomePage


urlpatterns= [
    path("", HomePage.as_view(), name="home"),
    
]

