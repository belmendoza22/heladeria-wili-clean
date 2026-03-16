from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('registro/', views.registro_view, name='registro'),  # antes signup
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),  # antes menu
    path('agregar_carrito/', views.agregar_carrito, name='agregar_carrito'),  # antes add_to_cart
    path('carrito/', views.carrito, name='carrito'),  # antes view_cart
    path('categoria/<slug:categoria_slug>/', views.productos_categoria, name='productos_categoria'),  # antes categoria_detalle
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)