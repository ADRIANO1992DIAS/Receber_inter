from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Login
    path("", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),

    # Admin
    path("admin/", admin.site.urls),

    # Demais rotas do app
    path("", include("billing.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
