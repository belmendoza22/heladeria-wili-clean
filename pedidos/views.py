from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from django.db.models import F, Sum, Count
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
import datetime
from .decorators import rol_requerido, admin_required, empleado_required
from django.db import models
from .forms import SignUpForm

from .models import (
    Sabor, Addon, Carrito, CartItem, Categoria,
    Producto, Tamano, ProductoTamano, Rol, Permiso, 
    RolPermiso, Profile, UnidadMedida, Insumo,
    Proveedor, Receta, Compra, DetalleCompra, Pedido,
    DetallePedido, Caja, Ingreso, Egreso, Promocion)

# Vistas de autenticación
def registro_view(request): 
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('menu')
    else:
        form = SignUpForm()
    return render(request, 'registration/registro.html', {'form': form})

def login_view(request):
    # Limpiar mensajes anteriores
    from django.contrib.messages import get_messages
    storage = get_messages(request)
    list(storage)

    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )
        if user:
            login(request, user)
            try:
                rol = user.profile.rol.nombre
            except AttributeError:
                rol = None

            if rol == 'Administrador':
                return redirect('admin_dashboard')
            elif rol == 'Empleado':
                return redirect('empleado_home')
            else:
                return redirect('menu')

        messages.error(request, 'Usuario o contraseña incorrectos')
    return render(request, 'registration/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# Vistas de categorías y productos
@method_decorator(login_required, name='dispatch')
class CategoriaListView(ListView):
    model = Categoria
    template_name = 'categorias/lista.html'
    context_object_name = 'categorias'

@login_required
def menu(request):
    categorias = Categoria.objects.all()
    sabores = Sabor.objects.filter(activo=True)
    productos_destacados = Producto.objects.filter(destacado=True)[:6]
    
    for producto in productos_destacados:
        producto.tamanos = ProductoTamano.objects.filter(producto=producto).select_related('tamano')
    
    carrito_count = 0
    if request.user.is_authenticated:
        carrito = Carrito.objects.filter(user=request.user).first()
        if carrito:
            carrito_count = carrito.items.count()
    
    context = {
        'categorias': categorias,
        'sabores': sabores,
        'productos_destacados': productos_destacados,
        'carrito_count': carrito_count,
    }
    return render(request, 'menu.html', context)

@login_required
def productos_categoria(request, categoria_slug):
    categoria = get_object_or_404(Categoria, slug=categoria_slug)
    productos = Producto.objects.filter(categoria=categoria)
    tamanos = Tamano.objects.filter(activo=True)
    sabores = Sabor.objects.filter(categoria=categoria, activo=True)

    productos_con_precios = []
    for producto in productos:
        precios = ProductoTamano.objects.filter(
            producto=producto
        ).select_related('tamano')
        productos_con_precios.append({
            'producto': producto,
            'precios': precios,
        })

    context = {
        'categoria': categoria,
        'productos_con_precios': productos_con_precios,
        'tamanos': tamanos,
        'sabores': sabores,
    }
    return render(request, 'productos_categoria.html', context)

@login_required
def productos_categoria(request, categoria_slug):
    categoria = get_object_or_404(Categoria, slug=categoria_slug)
    productos = Producto.objects.filter(categoria=categoria)
    tamanos = Tamano.objects.filter(activo=True)
    sabores = Sabor.objects.filter(categoria=categoria, activo=True)

    # Filtro por búsqueda dentro de la categoría
    busqueda = request.GET.get('q', '')
    if busqueda:
        productos = productos.filter(nombre__icontains=busqueda)

    productos_con_precios = []
    for producto in productos:
        precios = ProductoTamano.objects.filter(
            producto=producto
        ).select_related('tamano')
        productos_con_precios.append({
            'producto': producto,
            'precios': precios,
        })

    context = {
        'categoria': categoria,
        'productos_con_precios': productos_con_precios,
        'tamanos': tamanos,
        'sabores': sabores,
        'busqueda': busqueda,
        'categorias': Categoria.objects.all(),
    }
    return render(request, 'productos/productos_categoria.html', context)


@login_required
def buscar_productos(request):
    busqueda = request.GET.get('q', '')
    categorias = Categoria.objects.all()
    productos_con_precios = []

    if busqueda:
        productos = Producto.objects.filter(
            nombre__icontains=busqueda
        ).select_related('categoria')

        for producto in productos:
            precios = ProductoTamano.objects.filter(
                producto=producto
            ).select_related('tamano')
            productos_con_precios.append({
                'producto': producto,
                'precios': precios,
            })

    context = {
        'productos_con_precios': productos_con_precios,
        'busqueda': busqueda,
        'categorias': categorias,
    }
    return render(request, 'productos/buscar.html', context)

# Vistas del carrito
@login_required
def agregar_carrito(request):
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        tamano_id = request.POST.get('tamano_id')
        sabor_ids = request.POST.getlist('sabor_ids[]')
        cantidad = int(request.POST.get('cantidad', 1))

        producto = get_object_or_404(Producto, id=producto_id)
        tamano = get_object_or_404(Tamano, id=tamano_id, activo=True)

        # ── VALIDAR STOCK ──────────────────────────────────────────
        # 1. Verificar stock físico del producto terminado
        carrito_obj, _ = Carrito.objects.get_or_create(user=request.user)
        ya_en_carrito = CartItem.objects.filter(
            carrito=carrito_obj,
            producto=producto,
            tamano=tamano
        ).first()
        cantidad_en_carrito = ya_en_carrito.cantidad if ya_en_carrito else 0
        total_solicitado = cantidad_en_carrito + cantidad

        if producto.stock > 0 and total_solicitado > producto.stock:
            return JsonResponse({
                'success': False,
                'error': f'Stock insuficiente. Solo hay {producto.stock} '
                         f'unidades disponibles de {producto.nombre}.'
            })

        # 2. Verificar stock de insumos por receta
        recetas = Receta.objects.filter(producto=producto)
        insumos_faltantes = []
        for receta in recetas:
            insumo = receta.insumo
            necesario = receta.cantidad_requerida * total_solicitado
            if insumo.stock_actual < necesario:
                disponible = int(
                    insumo.stock_actual / receta.cantidad_requerida
                )
                insumos_faltantes.append(
                    f'{insumo.nombre} '
                    f'(disponible para {disponible} unidades)'
                )

        if insumos_faltantes:
            return JsonResponse({
                'success': False,
                'error': f'Stock de insumos insuficiente: '
                         f'{", ".join(insumos_faltantes)}'
            })

        # ── PRECIO ─────────────────────────────────────────────────
        try:
            pt = ProductoTamano.objects.get(
                producto=producto, tamano=tamano
            )
            precio_base = pt.precio
        except ProductoTamano.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'El tamaño no está disponible para este producto.'
            })

        sabores = Sabor.objects.filter(id__in=sabor_ids)
        extra_sabores = sum(s.precio_extra for s in sabores)
        precio_unitario = precio_base + extra_sabores

        # ── AGREGAR AL CARRITO ─────────────────────────────────────
        item, created = CartItem.objects.get_or_create(
            carrito=carrito_obj,
            producto=producto,
            tamano=tamano,
            defaults={
                'cantidad': cantidad,
                'precio_unitario': precio_unitario
            }
        )
        if not created:
            item.cantidad += cantidad
            item.save()

        item.sabores.set(sabores)

        return JsonResponse({
            'success': True,
            'message': f'{producto.nombre} agregado al carrito.'
        })

    return JsonResponse({
        'success': False,
        'error': 'Método no permitido'
    })
    
@login_required
def carrito(request):
    carrito, _ = Carrito.objects.get_or_create(user=request.user)
    items = carrito.items.all()
    for item in items:
        item.subtotal = item.precio_unitario * item.cantidad
    total = sum(item.subtotal for item in items)
    return render(request, 'carrito.html', {'items': items, 'total': total})

@login_required
def eliminar_item_carrito(request, item_id):
    if request.method == 'POST':
        item = get_object_or_404(CartItem, id=item_id, carrito__user=request.user)
        item.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@admin_required
def dashboard_admin(request):
    from django.contrib.auth.models import User
    pedidos_hoy = Pedido.objects.filter(
        fecha_pedido__date=timezone.now().date()
    ).count()
    pedidos_pendientes_count = Pedido.objects.filter(
        estado__in=['pendiente', 'confirmado']
    ).count()
    insumos_bajos = Insumo.objects.filter(
        stock_actual__lte=models.F('stock_minimo')
    ).count()
    total_usuarios = User.objects.count()

    context = {
        'pedidos_hoy': pedidos_hoy,
        'pedidos_pendientes': pedidos_pendientes_count,
        'insumos_bajos': insumos_bajos,
        'total_usuarios': total_usuarios,
    }
    return render(request, 'dashboard/admin/home.html', context)

@empleado_required
def dashboard_emple(request):
    pedidos = Pedido.objects.filter(
        estado__in=['pendiente', 'confirmado', 'en_preparacion']
    ).order_by('fecha_pedido')[:10]

    caja_abierta = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    return render(request, 'dashboard/empleado/home.html', {
        'pedidos': pedidos,
        'caja_abierta': caja_abierta,
    })
    
    
@empleado_required
def pedidos_pendientes(request):
    pedidos = Pedido.objects.filter(
        estado__in=['pendiente', 'confirmado']
    ).order_by('fecha_pedido')
    return render(request, 'dashboard/empleado/pedidos_pendientes.html', {'pedidos': pedidos})

#ABM Productos
@admin_required
def gestion_productos(request):
    productos = Producto.objects.select_related('categoria').all().order_by('categoria__nombre', 'nombre')
    categorias = Categoria.objects.all()
    context = {
        'productos': productos,
        'categorias': categorias,
    }
    return render(request, 'dashboard/admin/productos.html', context)

@admin_required
def crear_producto(request):
    categorias = Categoria.objects.all()
    tamanos = Tamano.objects.filter(activo=True)
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion', '')
        categoria_id = request.POST.get('categoria')
        precio_base = request.POST.get('precio_base')
        stock = request.POST.get('stock', 0)
        destacado = request.POST.get('destacado') == 'on'
        imagen = request.FILES.get('imagen')

        categoria = get_object_or_404(Categoria, id=categoria_id)
        producto = Producto.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            categoria=categoria,
            precio_base=precio_base,
            stock=stock,
            destacado=destacado,
            imagen=imagen,
        )
        # Guardar precios por tamaño
        for tamano in tamanos:
            precio_tamano = request.POST.get(f'precio_tamano_{tamano.id}')
            if precio_tamano:
                ProductoTamano.objects.create(
                    producto=producto,
                    tamano=tamano,
                    precio=precio_tamano
                )
        messages.success(request, f'Producto "{nombre}" creado exitosamente.')
        return redirect('gestion_productos')

    return render(request, 'dashboard/admin/producto_form.html', {
        'categorias': categorias,
        'tamanos': tamanos,
         'accion': 'Crear',
    })
    
@admin_required
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    categorias = Categoria.objects.all()
    tamanos = Tamano.objects.filter(activo=True)
    precios_tamano = {pt.tamano_id: pt.precio for pt in ProductoTamano.objects.filter(producto=producto)}

    if request.method == 'POST':
        producto.nombre = request.POST.get('nombre')
        producto.descripcion = request.POST.get('descripcion', '')
        producto.categoria = get_object_or_404(Categoria, id=request.POST.get('categoria'))
        producto.precio_base = request.POST.get('precio_base')
        producto.stock = request.POST.get('stock', 0)
        producto.destacado = request.POST.get('destacado') == 'on'
        if request.FILES.get('imagen'):
            producto.imagen = request.FILES.get('imagen')
        producto.save()
        
        # Actualizar precios por tamaño
        for tamano in tamanos:
            precio_tamano = request.POST.get(f'precio_tamano_{tamano.id}')
            if precio_tamano:
                ProductoTamano.objects.update_or_create(
                    producto=producto,
                    tamano=tamano,
                    defaults={'precio': precio_tamano}
                )
        messages.success(request, f'Producto "{producto.nombre}" actualizado.')
        return redirect('gestion_productos')

    return render(request, 'dashboard/admin/producto_form.html', {
        'producto': producto,
        'categorias': categorias,
        'tamanos': tamanos,
        'precios_tamano': precios_tamano,
        'accion': 'Editar',
    })
    
@admin_required
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f'Producto "{nombre}" eliminado.')
    return redirect('gestion_productos')

@admin_required
def gestion_insumos(request):
    insumos = Insumo.objects.select_related(
        'unidad_medida'
    ).all().order_by('nombre')
    
    # Detectar insumos con stock bajo
    insumos_bajos = insumos.filter(
        stock_actual__lte=models.F('stock_minimo')
    )
    
    context = {
        'insumos': insumos,
        'insumos_bajos_count': insumos_bajos.count(),
    }
    return render(request, 'dashboard/admin/insumos.html', context)


@admin_required
def crear_insumo(request):
    unidades = UnidadMedida.objects.all()
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion', '')
        unidad_id = request.POST.get('unidad_medida')
        stock_en_unidad = float(request.POST.get('stock_actual', 0))
        stock_minimo = float(request.POST.get('stock_minimo', 0))
        precio_unitario = request.POST.get('precio_unitario_promedio', 0)

        unidad = get_object_or_404(UnidadMedida, id=unidad_id)
        # Convertir a unidad base para almacenar
        stock_base = stock_en_unidad * float(unidad.factor_conversion)
        stock_min_base = stock_minimo * float(unidad.factor_conversion)

        Insumo.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            unidad_medida=unidad,
            stock_actual=stock_base,
            stock_minimo=stock_min_base,
            precio_unitario_promedio=precio_unitario,
        )
        messages.success(request, f'Insumo "{nombre}" creado exitosamente.')
        return redirect('gestion_insumos')

    return render(request, 'dashboard/admin/insumo_form.html', {
        'unidades': unidades,
        'accion': 'Crear',
    })


@admin_required
def editar_insumo(request, insumo_id):
    insumo = get_object_or_404(Insumo, id=insumo_id)
    unidades = UnidadMedida.objects.all()

    if request.method == 'POST':
        unidad_id = request.POST.get('unidad_medida')
        stock_en_unidad = float(request.POST.get('stock_actual', 0))
        stock_minimo = float(request.POST.get('stock_minimo', 0))

        unidad = get_object_or_404(UnidadMedida, id=unidad_id)
        stock_base = stock_en_unidad * float(unidad.factor_conversion)
        stock_min_base = stock_minimo * float(unidad.factor_conversion)

        insumo.nombre = request.POST.get('nombre')
        insumo.descripcion = request.POST.get('descripcion', '')
        insumo.unidad_medida = unidad
        insumo.stock_actual = stock_base
        insumo.stock_minimo = stock_min_base
        insumo.precio_unitario_promedio = request.POST.get(
            'precio_unitario_promedio', 0
        )
        insumo.save()
        messages.success(request, f'Insumo "{insumo.nombre}" actualizado.')
        return redirect('gestion_insumos')

    return render(request, 'dashboard/admin/insumo_form.html', {
        'insumo': insumo,
        'unidades': unidades,
        'accion': 'Editar',
    })


@admin_required
def eliminar_insumo(request, insumo_id):
    insumo = get_object_or_404(Insumo, id=insumo_id)
    if request.method == 'POST':
        nombre = insumo.nombre
        insumo.delete()
        messages.success(request, f'Insumo "{nombre}" eliminado.')
    return redirect('gestion_insumos')


@admin_required
def crear_unidad_medida(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        simbolo = request.POST.get('simbolo')
        UnidadMedida.objects.get_or_create(
            nombre=nombre,
            defaults={'simbolo': simbolo}
        )
        messages.success(request, f'Unidad "{nombre}" creada.')
        return redirect('gestion_insumos')
    return render(request, 'dashboard/admin/unidad_form.html')

# Control de Stock 
@admin_required
def control_stock(request):
    insumos = Insumo.objects.select_related('unidad_medida').all().order_by('nombre')
    insumos_bajos = insumos.filter(stock_actual__lte=F('stock_minimo'))
    proveedores = Proveedor.objects.all()
    compras = Compra.objects.select_related(
        'proveedor', 'empleado'
    ).all().order_by('-fecha')[:10]

    context = {
        'insumos': insumos,
        'insumos_bajos': insumos_bajos,
        'proveedores': proveedores,
        'compras': compras,
    }
    return render(request, 'dashboard/admin/stock.html', context)


@admin_required
def registrar_compra(request):
    # Verificar caja abierta de cualquier empleado
    caja_abierta = Caja.objects.filter(estado='abierta').first()

    if not caja_abierta:
        messages.error(
            request,
            'No hay ninguna caja abierta. '
            'Un empleado debe abrir la caja antes de registrar compras.'
        )
        return redirect('control_stock')

    proveedores = Proveedor.objects.all()
    insumos = Insumo.objects.select_related('unidad_medida').all()

    if request.method == 'POST':
        proveedor_id = request.POST.get('proveedor')
        proveedor = get_object_or_404(Proveedor, id=proveedor_id)

        compra = Compra.objects.create(
            proveedor=proveedor,
            empleado=request.user,
            total_compra=0,
        )

        total = 0
        insumo_ids = request.POST.getlist('insumo_id[]')
        cantidades = request.POST.getlist('cantidad[]')
        precios = request.POST.getlist('precio_unitario[]')

        for insumo_id, cantidad, precio in zip(
            insumo_ids, cantidades, precios
        ):
            if insumo_id and cantidad and precio:
                insumo = get_object_or_404(Insumo, id=insumo_id)
                cantidad_val = float(cantidad)
                precio_val = int(precio)
                DetalleCompra.objects.create(
                    compra=compra,
                    insumo=insumo,
                    cantidad=cantidad_val,
                    precio_unitario=precio_val,
                )
                total += cantidad_val * precio_val

        compra.total_compra = total
        compra.save()

        # Registrar egreso en caja
        Egreso.objects.create(
            caja=caja_abierta,
            responsable=request.user,
            monto=total,
            motivo=f'Compra de insumos — Proveedor: {proveedor.nombre}',
            tipo_egreso='compra_insumos',
        )

        messages.success(
            request,
            f'Compra registrada. Total: G. {total:,.0f}. '
            f'Egreso registrado en caja.'
        )
        return redirect('control_stock')

    return render(request, 'dashboard/admin/registrar_compra.html', {
        'proveedores': proveedores,
        'insumos': insumos,
        'caja': caja_abierta,
    })

@admin_required  
def historial_stock(request):
    insumo_id = request.GET.get('insumo_id')
    insumos = Insumo.objects.all()
    detalles = []

    if insumo_id:
        insumo = get_object_or_404(Insumo, id=insumo_id)
        detalles = DetalleCompra.objects.filter(
            insumo=insumo
        ).select_related('compra__proveedor').order_by('-compra__fecha')
    else:
        insumo = None

    context = {
        'insumos': insumos,
        'insumo_seleccionado': insumo,
        'detalles': detalles,
    }
    return render(request, 'dashboard/admin/historial_stock.html', context)

# ABM Proveedores
@admin_required
def registrar_proveedor(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        ruc = request.POST.get('ruc')
        contacto = request.POST.get('contacto', '')
        telefono = request.POST.get('telefono', '')
        direccion = request.POST.get('direccion', '')

        Proveedor.objects.create(
            nombre=nombre,
            ruc=ruc,
            contacto=contacto,
            telefono=telefono,
            direccion=direccion,
        )
        messages.success(request, f'Proveedor "{nombre}" registrado.')
        return redirect('gestion_proveedores')

    return render(request, 'dashboard/admin/proveedor_form.html', {
        'accion': 'Crear',
    })

@admin_required
def gestion_proveedores(request):
    proveedores = Proveedor.objects.all().order_by('nombre')
    context = {
        'proveedores': proveedores,
    }
    return render(request, 'dashboard/admin/proveedores.html', context)


@admin_required
def editar_proveedor(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)

    if request.method == 'POST':
        proveedor.nombre = request.POST.get('nombre')
        proveedor.ruc = request.POST.get('ruc')
        proveedor.contacto = request.POST.get('contacto', '')
        proveedor.telefono = request.POST.get('telefono', '')
        proveedor.direccion = request.POST.get('direccion', '')
        proveedor.save()
        messages.success(request, f'Proveedor "{proveedor.nombre}" actualizado.')
        return redirect('gestion_proveedores')

    return render(request, 'dashboard/admin/proveedor_form.html', {
        'proveedor': proveedor,
        'accion': 'Editar',
    })


@admin_required
def eliminar_proveedor(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    if request.method == 'POST':
        nombre = proveedor.nombre
        proveedor.delete()
        messages.success(request, f'Proveedor "{nombre}" eliminado.')
    return redirect('gestion_proveedores')

# Gestión de pedidos — Empleado
@empleado_required
def registrar_pedido(request):
    # Verificar caja abierta
    caja_abierta = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    if not caja_abierta:
        messages.error(
            request,
            'Debés abrir la caja antes de registrar pedidos.'
        )
        return redirect('apertura_caja')

    clientes = User.objects.filter(profile__rol__nombre='Cliente')
    productos = Producto.objects.select_related('categoria').all()
    tamanos = Tamano.objects.filter(activo=True)

    precios_data = {}
    for pt in ProductoTamano.objects.select_related('producto', 'tamano').all():
        key = f"{pt.producto_id}_{pt.tamano_id}"
        precios_data[key] = int(pt.precio)

    if request.method == 'POST':
        # ... resto igual
        pass

    context = {
        'clientes': clientes,
        'productos': productos,
        'tamanos': tamanos,
        'precios_data': precios_data,
        'caja': caja_abierta,
    }
    return render(request, 'dashboard/empleado/registrar_pedido.html', context)


@empleado_required
def gestion_pedidos(request):
    estado = request.GET.get('estado', '')
    pedidos = Pedido.objects.select_related(
        'cliente', 'empleado_cajero'
    ).all().order_by('-fecha_pedido')

    if estado:
        pedidos = pedidos.filter(estado=estado)

    context = {
        'pedidos': pedidos,
        'estado_filtro': estado,
        'estados': Pedido.ESTADOS,
    }
    return render(request, 'dashboard/empleado/gestion_pedidos.html', context)


@empleado_required
def detalle_pedido(request, pedido_id):
    pedido = get_object_or_404(
        Pedido.objects.select_related('cliente', 'empleado_cajero'),
        id=pedido_id
    )
    detalles = pedido.detalles.select_related('producto', 'tamano').all()
    context = {
        'pedido': pedido,
        'detalles': detalles,
    }
    return render(request, 'dashboard/empleado/detalle_pedido.html', context)


@empleado_required
def actualizar_estado_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        estados_validos = [e[0] for e in Pedido.ESTADOS]

        if nuevo_estado in estados_validos:
            estado_anterior = pedido.estado
            pedido.estado = nuevo_estado
            pedido.save()

            # Descontar insumos cuando pasa a "en_preparacion"
            if nuevo_estado == 'en_preparacion' and estado_anterior != 'en_preparacion':
                insumos_faltantes = []
                for detalle in pedido.detalles.all():
                    recetas = Receta.objects.filter(producto=detalle.producto)
                    for receta in recetas:
                        insumo = receta.insumo
                        # cantidad_requerida está en unidad base (gramos/mL)
                        cantidad_necesaria = receta.cantidad_requerida * detalle.cantidad
                        if insumo.stock_actual >= cantidad_necesaria:
                            insumo.stock_actual -= cantidad_necesaria
                            insumo.ultima_operacion = (
                                f'Pedido #{pedido.id}: '
                                f'-{receta.cantidad_requerida * detalle.cantidad} unidades base'
                            )
                            insumo.save()
                        else:
                            # Mostrar en unidad legible
                            disponible_display = (
                                insumo.stock_actual /
                                insumo.unidad_medida.factor_conversion
                            )
                            insumos_faltantes.append(
                                f"{insumo.nombre}: necesitás "
                                f"{receta.cantidad_requerida * detalle.cantidad / insumo.unidad_medida.factor_conversion:.2f}"
                                f" {insumo.unidad_medida.simbolo}, "
                                f"hay {disponible_display:.2f} {insumo.unidad_medida.simbolo}"
                            )
                
    next_url = request.POST.get('next', 'gestion_pedidos')
    return redirect(next_url)

# Vista de despacho
@empleado_required
def vista_despacho(request):
    pedidos = Pedido.objects.filter(
        estado__in=['confirmado', 'en_preparacion']
    ).prefetch_related(
        'detalles__producto',
        'detalles__tamano',
    ).select_related('cliente').order_by('fecha_pedido')

    context = {
        'pedidos': pedidos,
        'estados': Pedido.ESTADOS,
    }
    return render(request, 'dashboard/empleado/despacho.html', context)

# Pedidos Online — Cliente
@login_required
def realizar_pedido_online(request):
    carrito_obj = Carrito.objects.filter(user=request.user).first()
    
    if not carrito_obj or not carrito_obj.items.exists():
        messages.error(request, 'Tu carrito está vacío.')
        return redirect('carrito')

    if request.method == 'POST':
        observaciones = request.POST.get('observaciones', '')
        
        # Crear el pedido desde el carrito
        pedido = Pedido.objects.create(
            cliente=request.user,
            tipo_pedido='online',
            observaciones=observaciones,
            estado='pendiente',
        )

        # Convertir items del carrito a detalles del pedido
        for item in carrito_obj.items.all():
            DetallePedido.objects.create(
                pedido=pedido,
                producto=item.producto,
                tamano=item.tamano,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
            )

        pedido.calcular_total()

        # Vaciar el carrito
        carrito_obj.items.all().delete()

        messages.success(
            request,
            f'¡Pedido #{pedido.id} realizado exitosamente! '
            f'Te avisaremos cuando esté listo para retirar.'
        )
        return redirect('mis_pedidos')

    # Calcular total del carrito
    items = carrito_obj.items.all()
    for item in items:
        item.subtotal = item.precio_unitario * item.cantidad
    total = sum(item.subtotal for item in items)

    return render(request, 'pedidos/confirmar_pedido.html', {
        'items': items,
        'total': total,
    })


@login_required
def mis_pedidos(request):
    pedidos = Pedido.objects.filter(
        cliente=request.user
    ).order_by('-fecha_pedido')

    context = {
        'pedidos': pedidos,
    }
    return render(request, 'pedidos/mis_pedidos.html', context)


@login_required
def cancelar_pedido(request, pedido_id):
    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        cliente=request.user
    )
    if request.method == 'POST':
        if pedido.estado == 'pendiente':
            pedido.estado = 'cancelado'
            pedido.save()
            messages.success(request, f'Pedido #{pedido.id} cancelado.')
        else:
            messages.error(
                request,
                'No podés cancelar un pedido que ya está en preparación.'
            )
    return redirect('mis_pedidos')

# Modificar pedido — Cliente
@login_required
def modificar_pedido(request, pedido_id):
    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        cliente=request.user
    )

    # Solo se puede modificar si está pendiente
    if pedido.estado != 'pendiente':
        messages.error(
            request,
            f'No podés modificar el pedido #{pedido.id} '
            f'porque ya está "{pedido.get_estado_display()}".'
        )
        return redirect('mis_pedidos')

    productos = Producto.objects.all()
    tamanos = Tamano.objects.filter(activo=True)
    detalles = pedido.detalles.select_related('producto', 'tamano').all()

    if request.method == 'POST':
        observaciones = request.POST.get('observaciones', '')
        pedido.observaciones = observaciones
        pedido.save()

        # Eliminar detalles anteriores
        pedido.detalles.all().delete()

        # Guardar nuevos detalles
        producto_ids = request.POST.getlist('producto_id[]')
        tamano_ids = request.POST.getlist('tamano_id[]')
        cantidades = request.POST.getlist('cantidad[]')
        precios = request.POST.getlist('precio_unitario[]')
        obs_detalles = request.POST.getlist('obs_detalle[]')

        for prod_id, tam_id, cantidad, precio, obs in zip(
            producto_ids, tamano_ids, cantidades, precios, obs_detalles
        ):
            if prod_id and cantidad and precio:
                DetallePedido.objects.create(
                    pedido=pedido,
                    producto_id=prod_id,
                    tamano_id=tam_id if tam_id else None,
                    cantidad=int(cantidad),
                    precio_unitario=int(precio),
                    observaciones=obs,
                )

        pedido.calcular_total()
        messages.success(
            request,
            f'Pedido #{pedido.id} modificado exitosamente.'
        )
        return redirect('mis_pedidos')

    context = {
        'pedido': pedido,
        'detalles': detalles,
        'productos': productos,
        'tamanos': tamanos,
    }
    return render(request, 'pedidos/modificar_pedido.html', context)

# Módulo de caja
@empleado_required
def apertura_caja(request):
    # Verificar si ya hay una caja abierta
    caja_abierta = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    if caja_abierta:
        messages.warning(
            request,
            f'Ya tenés una caja abierta (#{caja_abierta.id}). '
            f'Cerrala antes de abrir una nueva.'
        )
        return redirect('gestion_caja')

    if request.method == 'POST':
        monto_inicial = request.POST.get('monto_inicial', 0)
        caja = Caja.objects.create(
            empleado_cajero=request.user,
            monto_inicial=monto_inicial,
            estado='abierta',
        )
        messages.success(
            request,
            f'Caja #{caja.id} abierta exitosamente con G. {monto_inicial}.'
        )
        return redirect('gestion_caja')

    return render(request, 'dashboard/empleado/apertura_caja.html')


@empleado_required
def gestion_caja(request):
    caja_abierta = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    cajas_anteriores = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='cerrada'
    ).order_by('-fecha_apertura')[:5]

    context = {
        'caja': caja_abierta,
        'cajas_anteriores': cajas_anteriores,
    }

    if caja_abierta:
        ingresos = caja_abierta.ingresos.all().order_by('-fecha')
        egresos = caja_abierta.egresos.all().order_by('-fecha')
        total_ingresos = sum(i.monto for i in ingresos)
        total_egresos = sum(e.monto for e in egresos)
        balance = caja_abierta.monto_inicial + total_ingresos - total_egresos

        context.update({
            'ingresos': ingresos,
            'egresos': egresos,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'balance': balance,
        })

    return render(request, 'dashboard/empleado/gestion_caja.html', context)


@empleado_required
def registrar_ingreso(request):
    caja = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    if not caja:
        messages.error(request, 'No tenés una caja abierta.')
        return redirect('apertura_caja')

    if request.method == 'POST':
        monto = request.POST.get('monto')
        tipo_ingreso = request.POST.get('tipo_ingreso', 'otro')
        descripcion = request.POST.get('descripcion', '')

        Ingreso.objects.create(
            caja=caja,
            monto=monto,
            tipo_ingreso=tipo_ingreso,
            descripcion=descripcion,
        )
        messages.success(request, f'Ingreso de G. {monto} registrado.')
        return redirect('gestion_caja')

    return render(request, 'dashboard/empleado/registrar_ingreso.html', {
        'caja': caja,
        'tipos': Ingreso.TIPOS_INGRESO,
    })


@empleado_required
def registrar_egreso(request):
    caja = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    if not caja:
        messages.error(request, 'No tenés una caja abierta.')
        return redirect('apertura_caja')

    if request.method == 'POST':
        monto = float(request.POST.get('monto', 0))
        motivo = request.POST.get('motivo')
        tipo_egreso = request.POST.get('tipo_egreso', 'gasto_operativo')
        descripcion = request.POST.get('descripcion', '')

        # Calcular balance actual
        total_ingresos = sum(
            i.monto for i in caja.ingresos.all()
        )
        total_egresos = sum(
            e.monto for e in caja.egresos.all()
        )
        balance_actual = float(caja.monto_inicial) + float(total_ingresos) - float(total_egresos)

        # Verificar que no quede negativo
        if monto > balance_actual:
            messages.error(
                request,
                f'No podés registrar este egreso. '
                f'El balance actual es G. {balance_actual:,.0f} '
                f'y el egreso es G. {monto:,.0f}. '
                f'La caja no puede quedar negativa.'
            )
            return render(request, 'dashboard/empleado/registrar_egreso.html', {
                'caja': caja,
                'tipos': Egreso.TIPOS_EGRESO,
                'balance_actual': balance_actual,
            })

        Egreso.objects.create(
            caja=caja,
            responsable=request.user,
            monto=monto,
            motivo=motivo,
            tipo_egreso=tipo_egreso,
            descripcion=descripcion,
        )
        messages.success(request, f'Egreso de G. {monto:,.0f} registrado.')
        return redirect('gestion_caja')

    # Calcular balance para mostrar
    total_ingresos = sum(i.monto for i in caja.ingresos.all())
    total_egresos = sum(e.monto for e in caja.egresos.all())
    balance_actual = float(caja.monto_inicial) + float(total_ingresos) - float(total_egresos)

    return render(request, 'dashboard/empleado/registrar_egreso.html', {
        'caja': caja,
        'tipos': Egreso.TIPOS_EGRESO,
        'balance_actual': balance_actual,
    })
    

@empleado_required
def cierre_caja(request):
    caja = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    if not caja:
        messages.error(request, 'No tenés una caja abierta.')
        return redirect('gestion_caja')

    if request.method == 'POST':
        monto_contado = request.POST.get('monto_contado', 0)
        caja.cerrar(monto_contado)
        messages.success(
            request,
            f'Caja #{caja.id} cerrada exitosamente.'
        )
        return redirect('resumen_caja', caja_id=caja.id)

    # Calcular totales para mostrar antes del cierre
    ingresos = caja.ingresos.all()
    egresos = caja.egresos.all()
    total_ingresos = sum(i.monto for i in ingresos)
    total_egresos = sum(e.monto for e in egresos)
    balance_sistema = caja.monto_inicial + total_ingresos - total_egresos

    context = {
        'caja': caja,
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'balance_sistema': balance_sistema,
    }
    return render(request, 'dashboard/empleado/cierre_caja.html', context)


@empleado_required
def resumen_caja(request, caja_id):
    caja = get_object_or_404(Caja, id=caja_id)
    ingresos = caja.ingresos.all()
    egresos = caja.egresos.all()
    total_ingresos = sum(i.monto for i in ingresos)
    total_egresos = sum(e.monto for e in egresos)
    diferencia = caja.monto_final_contado - caja.monto_final_sistema if caja.monto_final_contado and caja.monto_final_sistema else 0

    context = {
        'caja': caja,
        'ingresos': ingresos,
        'egresos': egresos,
        'total_ingresos': total_ingresos,
        'total_egresos': total_egresos,
        'diferencia': diferencia,
    }
    return render(request, 'dashboard/empleado/resumen_caja.html', context)

# Reportes
@admin_required
def reportes(request):
    return render(request, 'dashboard/admin/reportes.html')


@admin_required
def reporte_ventas(request):
    # Filtro por fechas
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    pedidos = Pedido.objects.filter(
        estado__in=['listo', 'entregado']
    ).order_by('-fecha_pedido')

    if fecha_inicio:
        pedidos = pedidos.filter(fecha_pedido__date__gte=fecha_inicio)
    if fecha_fin:
        pedidos = pedidos.filter(fecha_pedido__date__lte=fecha_fin)

    total_ventas = pedidos.aggregate(total=Sum('total'))['total'] or 0
    cantidad_pedidos = pedidos.count()

    # Ventas por día de la semana
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves',
                   'Viernes', 'Sábado', 'Domingo']
    ventas_por_dia = []
    for i, dia in enumerate(dias_semana):
        total_dia = pedidos.filter(
            fecha_pedido__week_day=i+2
        ).aggregate(total=Sum('total'))['total'] or 0
        cant_dia = pedidos.filter(
            fecha_pedido__week_day=i+2
        ).count()
        ventas_por_dia.append({
            'dia': dia,
            'total': total_dia,
            'cantidad': cant_dia,
        })

    context = {
        'pedidos': pedidos[:20],
        'total_ventas': total_ventas,
        'cantidad_pedidos': cantidad_pedidos,
        'ventas_por_dia': ventas_por_dia,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }
    return render(request, 'dashboard/admin/reporte_ventas.html', context)


@admin_required
def reporte_productos(request):
    # Productos más y menos vendidos
    productos_mas = DetallePedido.objects.filter(
        pedido__estado__in=['listo', 'entregado']
    ).values(
        'producto__nombre'
    ).annotate(
        total_vendido=Sum('cantidad'),
        ingresos=Sum('subtotal')
    ).order_by('-total_vendido')[:10]

    productos_menos = DetallePedido.objects.filter(
        pedido__estado__in=['listo', 'entregado']
    ).values(
        'producto__nombre'
    ).annotate(
        total_vendido=Sum('cantidad'),
        ingresos=Sum('subtotal')
    ).order_by('total_vendido')[:10]

    context = {
        'productos_mas': productos_mas,
        'productos_menos': productos_menos,
    }
    return render(request, 'dashboard/admin/reporte_productos.html', context)


@admin_required
def reporte_clientes(request):
    # Top 10 clientes con más compras
    from django.contrib.auth.models import User
    top_clientes = Pedido.objects.filter(
        estado__in=['listo', 'entregado'],
        cliente__isnull=False
    ).values(
        'cliente__username',
        'cliente__first_name',
        'cliente__last_name',
    ).annotate(
        total_pedidos=Count('id'),
        total_gastado=Sum('total')
    ).order_by('-total_gastado')[:10]

    context = {
        'top_clientes': top_clientes,
    }
    return render(request, 'dashboard/admin/reporte_clientes.html', context)


@admin_required
def reporte_costos(request):
    # Reporte de costos y ganancias mensuales
    mes = request.GET.get('mes', timezone.now().month)
    anio = request.GET.get('anio', timezone.now().year)

    mes = int(mes)
    anio = int(anio)

    # Ventas del mes
    ventas_mes = Pedido.objects.filter(
        estado__in=['listo', 'entregado'],
        fecha_pedido__month=mes,
        fecha_pedido__year=anio,
    ).aggregate(total=Sum('total'))['total'] or 0

    # Compras del mes
    compras_mes = Compra.objects.filter(
        fecha__month=mes,
        fecha__year=anio,
    ).aggregate(total=Sum('total_compra'))['total'] or 0

    # Egresos del mes
    egresos_mes = Egreso.objects.filter(
        fecha__month=mes,
        fecha__year=anio,
    ).aggregate(total=Sum('monto'))['total'] or 0

    ganancia = ventas_mes - compras_mes - egresos_mes

    # Lista de meses para el filtro
    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]

    context = {
        'ventas_mes': ventas_mes,
        'compras_mes': compras_mes,
        'egresos_mes': egresos_mes,
        'ganancia': ganancia,
        'mes_actual': mes,
        'anio_actual': anio,
        'meses': meses,
    }
    return render(request, 'dashboard/admin/reporte_costos.html', context)

# Ticket de pago
@empleado_required
def confirmar_pago(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # Verificar caja abierta
    caja_abierta = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    if not caja_abierta:
        messages.error(
            request,
            'No podés confirmar el pago sin una caja abierta. '
            'Abrí la caja primero.'
        )
        return redirect('apertura_caja')

    if request.method == 'POST':
        metodo_pago = request.POST.get('metodo_pago', 'efectivo')
        pedido.metodo_pago = metodo_pago
        pedido.pago_confirmado = True
        pedido.estado = 'entregado'
        pedido.save()

        Ingreso.objects.create(
            caja=caja_abierta,
            pedido=pedido,
            monto=pedido.total,
            tipo_ingreso='venta',
            descripcion=f'Pedido #{pedido.id} — {metodo_pago}',
        )
        messages.success(request, 'Pago confirmado y registrado en caja.')
        return redirect('ticket_pedido', pedido_id=pedido.id)

    detalles = pedido.detalles.select_related('producto', 'tamano').all()
    return render(request, 'dashboard/empleado/confirmar_pago.html', {
        'pedido': pedido,
        'detalles': detalles,
        'metodos': Pedido.METODOS_PAGO,
        'caja': caja_abierta,
    })
    

def ticket_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    detalles = pedido.detalles.select_related('producto', 'tamano').all()
    return render(request, 'ticket/ticket.html', {
        'pedido': pedido,
        'detalles': detalles,
    })
    
# ABM usuarios
@admin_required
def gestion_usuarios(request):
    from django.contrib.auth.models import User
    usuarios = User.objects.select_related(
        'profile__rol'
    ).all().order_by('username')
    roles = Rol.objects.all()
    context = {
        'usuarios': usuarios,
        'roles': roles,
    }
    return render(request, 'dashboard/admin/usuarios.html', context)


@admin_required
def editar_usuario(request, usuario_id):
    from django.contrib.auth.models import User
    usuario = get_object_or_404(User, id=usuario_id)
    roles = Rol.objects.all()

    if request.method == 'POST':
        usuario.first_name = request.POST.get('first_name', '')
        usuario.last_name = request.POST.get('last_name', '')
        usuario.email = request.POST.get('email', '')
        usuario.save()

        perfil, _ = Profile.objects.get_or_create(user=usuario)
        rol_id = request.POST.get('rol_id')
        if rol_id:
            perfil.rol = get_object_or_404(Rol, id=rol_id)
        perfil.phone = request.POST.get('phone', '')
        perfil.address = request.POST.get('address', '')
        perfil.save()

        messages.success(
            request,
            f'Usuario "{usuario.username}" actualizado.'
        )
        return redirect('gestion_usuarios')

    return render(request, 'dashboard/admin/usuario_form.html', {
        'usuario': usuario,
        'roles': roles,
    })


@admin_required
def eliminar_usuario(request, usuario_id):
    from django.contrib.auth.models import User
    usuario = get_object_or_404(User, id=usuario_id)
    if request.method == 'POST':
        if usuario == request.user:
            messages.error(request, 'No podés eliminarte a vos mismo.')
            return redirect('gestion_usuarios')
        username = usuario.username
        usuario.delete()
        messages.success(request, f'Usuario "{username}" eliminado.')
    return redirect('gestion_usuarios')


@admin_required
def crear_usuario(request):
    from django.contrib.auth.models import User
    roles = Rol.objects.all()

    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        rol_id = request.POST.get('rol_id')

        if User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe.')
        else:
            usuario = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
            )
            perfil, _ = Profile.objects.get_or_create(user=usuario)
            if rol_id:
                perfil.rol = get_object_or_404(Rol, id=rol_id)
                perfil.save()

            messages.success(
                request,
                f'Usuario "{username}" creado exitosamente.'
            )
            return redirect('gestion_usuarios')

    return render(request, 'dashboard/admin/usuario_form.html', {
        'roles': roles,
        'accion': 'Crear',
    })
    
# Promociones
@admin_required
def gestion_promociones(request):
    from django.utils import timezone
    promociones = Promocion.objects.prefetch_related(
        'productos'
    ).all().order_by('-fecha_inicio')
    hoy = timezone.now().date()
    context = {
        'promociones': promociones,
        'hoy': hoy,
    }
    return render(
        request,
        'dashboard/admin/promociones.html',
        context
    )


@admin_required
def crear_promocion(request):
    productos = Producto.objects.all()
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion', '')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        tipo_descuento = request.POST.get('tipo_descuento')
        valor_descuento = request.POST.get('valor_descuento')
        productos_ids = request.POST.getlist('productos[]')

        promo = Promocion.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo_descuento=tipo_descuento,
            valor_descuento=valor_descuento,
            activo=True,
        )
        if productos_ids:
            promo.productos.set(productos_ids)

        messages.success(
            request,
            f'Promoción "{nombre}" creada exitosamente.'
        )
        return redirect('gestion_promociones')

    return render(request, 'dashboard/admin/promocion_form.html', {
        'productos': productos,
        'tipos': Promocion.TIPO_DESCUENTO,
        'accion': 'Crear',
    })


@admin_required
def editar_promocion(request, promo_id):
    promo = get_object_or_404(Promocion, id=promo_id)
    productos = Producto.objects.all()
    productos_seleccionados = promo.productos.values_list('id', flat=True)

    if request.method == 'POST':
        promo.nombre = request.POST.get('nombre')
        promo.descripcion = request.POST.get('descripcion', '')
        promo.fecha_inicio = request.POST.get('fecha_inicio')
        promo.fecha_fin = request.POST.get('fecha_fin')
        promo.tipo_descuento = request.POST.get('tipo_descuento')
        promo.valor_descuento = request.POST.get('valor_descuento')
        promo.activo = request.POST.get('activo') == 'on'
        promo.save()

        productos_ids = request.POST.getlist('productos[]')
        promo.productos.set(productos_ids)

        messages.success(
            request,
            f'Promoción "{promo.nombre}" actualizada.'
        )
        return redirect('gestion_promociones')

    return render(request, 'dashboard/admin/promocion_form.html', {
        'promo': promo,
        'productos': productos,
        'productos_seleccionados': list(productos_seleccionados),
        'tipos': Promocion.TIPO_DESCUENTO,
        'accion': 'Editar',
    })


@admin_required
def eliminar_promocion(request, promo_id):
    promo = get_object_or_404(Promocion, id=promo_id)
    if request.method == 'POST':
        nombre = promo.nombre
        promo.delete()
        messages.success(request, f'Promoción "{nombre}" eliminada.')
    return redirect('gestion_promociones')

# Stock segun recetas
@admin_required
def stock_producible(request):
    productos = Producto.objects.prefetch_related('recetas__insumo').all()
    resultado = []

    for producto in productos:
        recetas = producto.recetas.all()
        if not recetas:
            resultado.append({
                'producto': producto,
                'stock_producible': producto.stock,
                'sin_receta': True,
                'limitado_por': None,
            })
            continue

        # Calcular cuántas unidades se pueden producir
        # basándose en el insumo más limitante
        min_producible = None
        limitado_por = None

        for receta in recetas:
            insumo = receta.insumo
            if receta.cantidad_requerida > 0:
                producible = int(
                    insumo.stock_actual / receta.cantidad_requerida
                )
                if min_producible is None or producible < min_producible:
                    min_producible = producible
                    limitado_por = insumo.nombre

        resultado.append({
            'producto': producto,
            'stock_producible': min_producible or 0,
            'sin_receta': False,
            'limitado_por': limitado_por,
        })

    return render(
        request,
        'dashboard/admin/stock_producible.html',
        {'resultado': resultado}
    )


@admin_required
def actualizar_stock_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        nuevo_stock = int(request.POST.get('stock', 0))
        stock_anterior = producto.stock
        producto.stock = nuevo_stock
        producto.save()
        messages.success(
            request,
            f'Stock de "{producto.nombre}" actualizado: '
            f'{stock_anterior} → {nuevo_stock}.'
        )
    return redirect('stock_producible')

# Recetas
@admin_required
def gestion_recetas(request):
    recetas = Receta.objects.select_related(
        'producto__categoria', 'insumo__unidad_medida'
    ).all().order_by('producto__nombre')
    productos = Producto.objects.all().order_by('nombre')
    insumos = Insumo.objects.all().order_by('nombre')
    context = {
        'recetas': recetas,
        'productos': productos,
        'insumos': insumos,
    }
    return render(request, 'dashboard/admin/recetas.html', context)


@admin_required
def crear_receta(request):
    if request.method == 'POST':
        producto_id = request.POST.get('producto')
        insumo_id = request.POST.get('insumo')
        cantidad = request.POST.get('cantidad_requerida')

        # Verificar si ya existe
        if Receta.objects.filter(
            producto_id=producto_id,
            insumo_id=insumo_id
        ).exists():
            messages.error(
                request,
                'Ya existe una receta para ese producto e insumo.'
            )
        else:
            Receta.objects.create(
                producto_id=producto_id,
                insumo_id=insumo_id,
                cantidad_requerida=cantidad,
            )
            messages.success(request, 'Receta creada exitosamente.')
        return redirect('gestion_recetas')

    productos = Producto.objects.all().order_by('nombre')
    insumos = Insumo.objects.all().order_by('nombre')
    return render(request, 'dashboard/admin/receta_form.html', {
        'productos': productos,
        'insumos': insumos,
        'accion': 'Crear',
    })


@admin_required
def editar_receta(request, receta_id):
    receta = get_object_or_404(Receta, id=receta_id)
    if request.method == 'POST':
        receta.producto_id = request.POST.get('producto')
        receta.insumo_id = request.POST.get('insumo')
        receta.cantidad_requerida = request.POST.get('cantidad_requerida')
        receta.save()
        messages.success(request, 'Receta actualizada.')
        return redirect('gestion_recetas')

    productos = Producto.objects.all().order_by('nombre')
    insumos = Insumo.objects.all().order_by('nombre')
    return render(request, 'dashboard/admin/receta_form.html', {
        'receta': receta,
        'productos': productos,
        'insumos': insumos,
        'accion': 'Editar',
    })


@admin_required
def eliminar_receta(request, receta_id):
    receta = get_object_or_404(Receta, id=receta_id)
    if request.method == 'POST':
        receta.delete()
        messages.success(request, 'Receta eliminada.')
    return redirect('gestion_recetas')

# Modulo de producción
@admin_required
def registrar_produccion(request):
    productos = Producto.objects.prefetch_related(
        'recetas__insumo__unidad_medida'
    ).all().order_by('nombre')

    if request.method == 'POST':
        producto_id = request.POST.get('producto')
        cantidad_producida = int(request.POST.get('cantidad_producida', 0))
        observaciones = request.POST.get('observaciones', '')

        if cantidad_producida <= 0:
            messages.error(request, 'La cantidad debe ser mayor a 0.')
            return redirect('registrar_produccion')

        producto = get_object_or_404(Producto, id=producto_id)
        recetas = Receta.objects.filter(
            producto=producto
        ).select_related('insumo')

        if not recetas.exists():
            messages.error(
                request,
                f'El producto "{producto.nombre}" no tiene receta cargada.'
            )
            return redirect('registrar_produccion')

        # Verificar que hay suficientes insumos
        insumos_faltantes = []
        for receta in recetas:
            insumo = receta.insumo
            necesario = receta.cantidad_requerida * cantidad_producida
            if insumo.stock_actual < necesario:
                insumos_faltantes.append(
                    f'{insumo.nombre}: necesitás {necesario} '
                    f'{insumo.unidad_medida.simbolo}, '
                    f'hay {insumo.stock_actual}'
                )

        if insumos_faltantes:
            messages.error(
                request,
                f'Insumos insuficientes: {" | ".join(insumos_faltantes)}'
            )
            return redirect('registrar_produccion')

        # Descontar insumos y actualizar última operación
        for receta in recetas:
            insumo = receta.insumo
            insumo.stock_actual -= receta.cantidad_requerida * cantidad_producida
            insumo.ultima_operacion = f'Producción: {cantidad_producida} x {producto.nombre}'
            insumo.save()

        # Sumar al stock de productos terminados
        producto.stock += cantidad_producida
        producto.save()

        messages.success(
            request,
            f'Producción registrada: {cantidad_producida} unidades de '
            f'"{producto.nombre}". Stock actualizado a {producto.stock}.'
        )
        return redirect('historial_produccion')

    # Calcular producible por producto
    productos_con_info = []
    for producto in productos:
        recetas = producto.recetas.all()
        if recetas:
            min_producible = None
            limitante = None
            detalle_receta = []
            for receta in recetas:
                insumo = receta.insumo
                if receta.cantidad_requerida > 0:
                    producible = int(
                        insumo.stock_actual / receta.cantidad_requerida
                    )
                    if min_producible is None or producible < min_producible:
                        min_producible = producible
                        limitante = insumo.nombre
                detalle_receta.append({
                    'insumo': insumo.nombre,
                    'cantidad': receta.cantidad_requerida,
                    'unidad': insumo.unidad_medida.simbolo,
                    'stock': insumo.stock_actual,
                })
            productos_con_info.append({
                'producto': producto,
                'producible': min_producible or 0,
                'limitante': limitante,
                'receta': detalle_receta,
            })
        else:
            productos_con_info.append({
                'producto': producto,
                'producible': None,
                'limitante': None,
                'receta': [],
            })

    return render(request, 'dashboard/admin/registrar_produccion.html', {
        'productos_con_info': productos_con_info,
    })


@admin_required
def historial_produccion(request):
    # Usamos el campo ultima_operacion de los insumos para rastrear
    # En una versión más completa se agregaría un modelo ProduccionLog
    from django.contrib.auth.models import User
    productos = Producto.objects.all().order_by('nombre')
    return render(request, 'dashboard/admin/historial_produccion.html', {
        'productos': productos,
    })