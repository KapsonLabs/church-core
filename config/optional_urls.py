from django.urls import include, path

from .urls import urlpatterns

urlpatterns += [
    path("api/v1/crm/", include("apps.crm.urls")),
    path("api/v1/info/", include("apps.info.urls")),
    path("api/v1/kpis/", include("apps.kpis.urls")),
]
