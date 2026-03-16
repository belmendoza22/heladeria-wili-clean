from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    Sabor, Addon, Carrito, CartItem, Categoria,
    Producto, Tamano, ProductoTamano, Profile)

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'perfil'

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(Sabor)
admin.site.register(Addon)
admin.site.register(Carrito)
admin.site.register(CartItem)
admin.site.register(Categoria)
admin.site.register(Producto)
admin.site.register(Tamano)
admin.site.register(ProductoTamano)

