from django.contrib.auth.models import User
from django.views.generic import DetailView

class baseHtml(DetailView):
    template_name= "base.html"
    def get_context_data(self, **kwargs):
        context= super().get_context_data(**kwargs)
        context["usuario"]= User.objects.all()
        print(context)
    
        return context