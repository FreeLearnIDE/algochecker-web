from django.conf.urls import url, include
from django.contrib import admin

urlpatterns = [
    url(r'^', include('webapp.urls.base')),
    url(r'^staff/', include('webapp.urls.staff')),
    url(r'^admin/', admin.site.urls)
]
