from django.contrib import admin
from django.urls import include, path

from machina import urls as machina_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include(machina_urls)),
]
