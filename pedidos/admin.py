from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import (
    # Modelos del menú
    Categoria, Sabor, Addon, Tamano, Producto, ProductoTamano,
    # Modelos del carrito y perfil
    Carrito, CartItem, Profile,
    # Modelos de gestión (insumos, compras, etc.)
    UnidadMedida, Insumo, Proveedor, Receta,
    Compra, DetalleCompra,
    Pedido, DetallePedido,
    Caja, Ingreso, Egreso,
    Promocion,
)

# --------------------------------------------
# Inline para Profile dentro de User
# --------------------------------------------
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Perfil'
    extra = 0
    
    def get_formset(self, request, obj=None, **kwargs):
        # Si es usuario nuevo, crear Profile vacío primero
        if obj is not None:
            Profile.objects.get_or_create(user=obj)
        return super().get_formset(request, obj, **kwargs)

class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# --------------------------------------------
# Modelos del menú
# --------------------------------------------
@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion_corta', 'slug')
    search_fields = ('nombre',)
    prepopulated_fields = {'slug': ('nombre',)}

    def descripcion_corta(self, obj):
        return obj.descripcion[:50] + '...' if len(obj.descripcion) > 50 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'

@admin.register(Sabor)
class SaborAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio_extra', 'activo')
    list_filter = ('activo', 'categoria')
    search_fields = ('nombre',)
    prepopulated_fields = {'slug': ('nombre',)}

@admin.register(Addon)
class AddonAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio_extra', 'insumo', 'activo')
    list_filter  = ('activo',)
    search_fields = ('nombre',)

@admin.register(Tamano)
class TamanoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio_extra', 'activo')
    list_filter = ('activo', 'categoria')
    prepopulated_fields = {'slug': ('nombre',)}

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio_base', 'stock')
    list_filter = ('categoria',)
    search_fields = ('nombre', 'descripcion')

@admin.register(ProductoTamano)
class ProductoTamanoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'tamano', 'precio')
    list_filter = ('producto__categoria', 'tamano')
    search_fields = ('producto__nombre',)

# --------------------------------------------
# Carrito y perfil
# --------------------------------------------
@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at')
    list_filter = ('created_at',)

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'carrito', 'producto', 'tamano', 'cantidad', 'precio_unitario')
    list_filter = ('carrito__user',)

# --------------------------------------------
# Insumos y proveedores
# --------------------------------------------
@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'simbolo')
    search_fields = ('nombre',)

@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'unidad_medida', 'stock_actual', 'stock_minimo', 'precio_unitario_promedio')
    list_filter = ('unidad_medida',)
    search_fields = ('nombre',)
    readonly_fields = ('ultima_actualizacion',)

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ruc', 'contacto', 'telefono')
    search_fields = ('nombre', 'ruc', 'contacto')

@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ('producto', 'insumo', 'cantidad_requerida')
    list_filter = ('producto__categoria', 'insumo')
    search_fields = ('producto__nombre', 'insumo__nombre')

# --------------------------------------------
# Compras
# --------------------------------------------
class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 1
    fields = ('insumo', 'cantidad', 'precio_unitario')

@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'proveedor', 'empleado', 'total_compra')
    list_filter = ('fecha', 'proveedor')
    search_fields = ('proveedor__nombre',)
    readonly_fields = ('total_compra',)
    inlines = [DetalleCompraInline]

# --------------------------------------------
# Pedidos
# --------------------------------------------
class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0
    fields = ('producto', 'tamano', 'cantidad', 'precio_unitario', 'subtotal', 'observaciones')
    readonly_fields = ('subtotal',)

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'fecha_pedido', 'estado', 'tipo_pedido', 'total')
    list_filter = ('estado', 'tipo_pedido', 'fecha_pedido')
    search_fields = ('cliente__username', 'cliente__email')
    readonly_fields = ('total',)
    inlines = [DetallePedidoInline]

@admin.register(DetallePedido)
class DetallePedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'producto', 'cantidad', 'subtotal')
    list_filter = ('pedido__estado',)

# --------------------------------------------
# Caja
# --------------------------------------------
@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ('id', 'empleado_cajero', 'fecha_apertura', 'estado', 'monto_inicial', 'monto_final_contado')
    list_filter = ('estado', 'fecha_apertura')
    search_fields = ('empleado_cajero__username',)

@admin.register(Ingreso)
class IngresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'caja', 'fecha', 'tipo_ingreso', 'monto', 'pedido')
    list_filter = ('tipo_ingreso', 'fecha')
    search_fields = ('descripcion',)

@admin.register(Egreso)
class EgresoAdmin(admin.ModelAdmin):
    list_display = ('id', 'caja', 'fecha', 'tipo_egreso', 'monto', 'motivo', 'responsable')
    list_filter = ('tipo_egreso', 'fecha')
    search_fields = ('motivo', 'descripcion')

# --------------------------------------------
# Promociones
# --------------------------------------------
@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'fecha_inicio', 'fecha_fin', 'tipo_descuento', 'valor_descuento', 'activo')
    list_filter = ('activo', 'tipo_descuento')
    filter_horizontal = ('productos',)
    search_fields = ('nombre',)