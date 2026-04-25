from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # Autenticación
    path('registro/', views.registro_view, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Menú y productos
    path('menu/', views.menu, name='menu'),
    path('categorias/', views.CategoriaListView.as_view(), name='categorias'),
    path('categoria/<slug:categoria_slug>/', views.productos_categoria, name='productos_categoria'),

    # Carrito
    path('carrito/', views.carrito, name='carrito'),
    path('agregar_carrito/', views.agregar_carrito, name='agregar_carrito'),
    path('eliminar-carrito/<int:item_id>/', views.eliminar_item_carrito, name='eliminar_item_carrito'),

    # Paneles
    path('admin-dashboard/', views.dashboard_admin, name='admin_dashboard'),
    path('empleado/home/', views.dashboard_emple, name='empleado_home'),
    path('pedidos-pendientes/', views.pedidos_pendientes, name='pedidos_pendientes'),

    # ABM Productos
    path('panel/productos/', views.gestion_productos, name='gestion_productos'),
    path('panel/productos/crear/', views.crear_producto, name='crear_producto'),
    path('panel/productos/editar/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('panel/productos/eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    
    # Productos cliente
    path('productos/buscar/', views.buscar_productos, name='buscar_productos'),
    
    # ABM Insumos
    path('panel/insumos/', views.gestion_insumos, name='gestion_insumos'),
    path('panel/insumos/crear/', views.crear_insumo, name='crear_insumo'),
    path('panel/insumos/editar/<int:insumo_id>/', views.editar_insumo, name='editar_insumo'),
    path('panel/insumos/eliminar/<int:insumo_id>/', views.eliminar_insumo, name='eliminar_insumo'),
    path('panel/unidades/crear/', views.crear_unidad_medida, name='crear_unidad_medida'),
    
    # Control de stock  
    path('panel/stock/', views.control_stock, name='control_stock'),
    path('panel/stock/compra/', views.registrar_compra, name='registrar_compra'),
    path('panel/stock/historial/', views.historial_stock, name='historial_stock'),
    
    # ABM Proveedores
    path('panel/proveedores/', views.gestion_proveedores, name='gestion_proveedores'),
    path('panel/proveedores/crear/', views.registrar_proveedor, name='registrar_proveedor'),
    path('panel/proveedores/editar/<int:proveedor_id>/', views.editar_proveedor, name='editar_proveedor'),
    path('panel/proveedores/eliminar/<int:proveedor_id>/', views.eliminar_proveedor, name='eliminar_proveedor'),
    
    # Gestión de pedidos
    path('panel/pedidos/', views.gestion_pedidos, name='gestion_pedidos'),
    path('panel/pedidos/registrar/', views.registrar_pedido, name='registrar_pedido'),
    path('panel/pedidos/<int:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),
    path('panel/pedidos/<int:pedido_id>/estado/', views.actualizar_estado_pedido, name='actualizar_estado_pedido'),
    
    # Vista de despacho
    path('panel/despacho/', views.vista_despacho, name='vista_despacho'),
    
    # Pedidos Online — Clientes
    path('pedido/confirmar/', views.realizar_pedido_online, name='realizar_pedido_online'),
    path('pedido/mis-pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('pedido/cancelar/<int:pedido_id>/', views.cancelar_pedido, name='cancelar_pedido'),
    
    # Modificar pedido
    path('pedido/modificar/<int:pedido_id>/', views.modificar_pedido, name='modificar_pedido'),
    
    # Módulo de caja
    path('panel/caja/', views.gestion_caja, name='gestion_caja'),
    path('panel/caja/abrir/', views.apertura_caja, name='apertura_caja'),
    path('panel/caja/ingreso/', views.registrar_ingreso, name='registrar_ingreso'),
    path('panel/caja/egreso/', views.registrar_egreso, name='registrar_egreso'),
    path('panel/caja/cerrar/', views.cierre_caja, name='cierre_caja'),
    path('panel/caja/resumen/<int:caja_id>/', views.resumen_caja, name='resumen_caja'),
    
    # Ticket de pago
    path('panel/pedidos/<int:pedido_id>/confirmar-pago/', views.confirmar_pago, name='confirmar_pago'),
    path('ticket/<int:pedido_id>/', views.ticket_pedido, name='ticket_pedido'),
    
    # Reportes
    path('panel/reportes/', views.reportes, name='reportes'),
    path('panel/reportes/ventas/', views.reporte_ventas, name='reporte_ventas'),
    path('panel/reportes/productos/', views.reporte_productos, name='reporte_productos'),
    path('panel/reportes/clientes/', views.reporte_clientes, name='reporte_clientes'),
    path('panel/reportes/costos/', views.reporte_costos, name='reporte_costos'),
    
    # ABM usuarios
    path('panel/usuarios/', views.gestion_usuarios, name='gestion_usuarios'),
    path('panel/usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('panel/usuarios/editar/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
    path('panel/usuarios/eliminar/<int:usuario_id>/', views.eliminar_usuario, name='eliminar_usuario'),
    
    # Promociones
    path('panel/promociones/', views.gestion_promociones, name='gestion_promociones'),
    path('panel/promociones/crear/', views.crear_promocion, name='crear_promocion'),
    path('panel/promociones/editar/<int:promo_id>/', views.editar_promocion, name='editar_promocion'),
    path('panel/promociones/eliminar/<int:promo_id>/', views.eliminar_promocion, name='eliminar_promocion'),
    
    # Stock segun recetas
    path('panel/stock-producible/', views.stock_producible, name='stock_producible'),
    path('panel/stock-producible/actualizar/<int:producto_id>/', views.actualizar_stock_producto, name='actualizar_stock_producto'),
    
    # Recetas
    path('panel/recetas/', views.gestion_recetas, name='gestion_recetas'),
    path('panel/recetas/crear/', views.crear_receta, name='crear_receta'),
    path('panel/recetas/editar/<int:receta_id>/', views.editar_receta, name='editar_receta'),
    path('panel/recetas/eliminar/<int:receta_id>/', views.eliminar_receta, name='eliminar_receta'),
    
    # Producción
    path('panel/produccion/', views.registrar_produccion, name='registrar_produccion'),
    path('panel/produccion/historial/', views.historial_produccion, name='historial_produccion'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)