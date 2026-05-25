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
from django.contrib.messages import get_messages
from django.utils import timezone
from django.db.models import Q as DQ
import datetime
from .decorators import rol_requerido, admin_required, empleado_required
from django.db import models
from .forms import SignUpForm

from .models import (
    Sabor, Addon, Carrito, CartItem, Categoria,
    Producto, Tamano, ProductoTamano, Rol, Permiso, 
    RolPermiso, Profile, UnidadMedida, Insumo,
    Proveedor, Receta, Compra, DetalleCompra, Pedido,
    DetallePedido, Caja, Ingreso, Egreso, Promocion,
    ProduccionLog)

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
    categorias           = Categoria.objects.all()
    categoria_kilo = Categoria.objects.filter(nombre__icontains='kilo').first()
    if categoria_kilo:
        sabores = Sabor.objects.filter(activo=True, categoria=categoria_kilo)
    else:
        sabores = Sabor.objects.filter(activo=True)
    productos_destacados = Producto.objects.filter(destacado=True)[:6]

    for producto in productos_destacados:
        producto.tamanos = ProductoTamano.objects.filter(
            producto=producto
        ).select_related('tamano')

    carrito_count = 0
    if request.user.is_authenticated:
        carrito = Carrito.objects.filter(user=request.user).first()
        if carrito:
            carrito_count = carrito.items.count()

    context = {
        'categorias':           categorias,
        'sabores':              sabores,
        'productos_destacados': productos_destacados,
        'carrito_count':        carrito_count,
    }
    return render(request, 'menu.html', context)

@login_required
def productos_categoria(request, categoria_slug):
    categoria = get_object_or_404(Categoria, slug=categoria_slug)
    busqueda  = request.GET.get('q', '')

    es_admin = (
        request.user.is_authenticated and
        hasattr(request.user, 'profile') and
        request.user.profile.rol and
        request.user.profile.rol.nombre == 'Administrador'
    )

    productos = Producto.objects.filter(categoria=categoria)
    if busqueda:
        productos = productos.filter(nombre__icontains=busqueda)

    sabores_qs = Sabor.objects.filter(activo=True).filter(DQ(categoria=categoria) | DQ(categorias_extra=categoria)
    ).distinct().select_related('insumo_stock', 'insumo_stock__unidad_medida', 'subcategoria').order_by('subcategoria__nombre', 'nombre')

    sabores = []
    for sabor in sabores_qs:
        disponible = True
        if not es_admin and sabor.insumo_stock:
            disponible = float(sabor.insumo_stock.stock_actual) > 0
        sabores.append({
            'id':            sabor.id,
            'nombre':        sabor.nombre,
            'imagen':        sabor.imagen.url if sabor.imagen else None,
            'descripcion':   sabor.descripcion,
            'disponible':    disponible,
            'subcategoria':  sabor.subcategoria.nombre if sabor.subcategoria else None,
        })


    from django.utils import timezone as tz
    from decimal import Decimal
    hoy = tz.now().date()

    productos_con_precios = []
    for producto in productos:
        precios_qs = ProductoTamano.objects.filter(
            producto=producto
        ).select_related('tamano')

        if not es_admin:
            precios_qs = precios_qs.filter(tamano__solo_produccion=False)

        if not es_admin and not precios_qs.exists():
            continue

        promo = producto.promociones_aplicadas.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
        ).first()

        precios_con_promo = []
        for pt in precios_qs:
            precio_original = pt.precio
            precio_final    = precio_original
            descuento_texto = None

            if promo:
                if promo.tipo_descuento == 'porcentaje':
                    descuento       = precio_original * Decimal(str(promo.valor_descuento)) / 100
                    precio_final    = precio_original - descuento
                    descuento_texto = f'{int(promo.valor_descuento)}% OFF'
                elif promo.tipo_descuento == 'monto_fijo':
                    precio_final    = max(Decimal('0'), precio_original - promo.valor_descuento)
                    descuento_texto = f'G. {int(promo.valor_descuento):,} OFF'.replace(',', '.')

            precios_con_promo.append({
                'tamano':          pt.tamano,
                'tamano_id':       pt.tamano.id,
                'precio_original': precio_original,
                'precio_final':    precio_final,
                'descuento_texto': descuento_texto,
                'promo_nombre':    promo.nombre if promo else None,
                'max_sabores':     pt.tamano.max_sabores,
            })

        productos_con_precios.append({
            'producto': producto,
            'precios':  precios_con_promo,
            'promo':    promo,
        })

    context = {
        'categoria':             categoria,
        'productos_con_precios': productos_con_precios,
        'sabores':               sabores,
        'busqueda':              busqueda,
        'categorias':            Categoria.objects.all(),
        'addons':                Addon.objects.filter(activo=True).filter(models.Q(categorias__isnull=True)|models.Q(categorias=categoria)).distinct().select_related('insumo'),
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
        tamano_id   = request.POST.get('tamano_id')
        sabor_ids   = request.POST.getlist('sabor_ids[]')
        addon_ids   = request.POST.getlist('addon_ids[]')
        cantidad    = int(request.POST.get('cantidad', 1))

        producto = get_object_or_404(Producto, id=producto_id)
        tamano   = get_object_or_404(Tamano, id=tamano_id, activo=True)

        carrito_obj, _ = Carrito.objects.get_or_create(user=request.user)
        ya_en_carrito  = CartItem.objects.filter(
            carrito=carrito_obj, producto=producto, tamano=tamano
        ).first()
        cantidad_en_carrito = ya_en_carrito.cantidad if ya_en_carrito else 0
        total_solicitado    = cantidad_en_carrito + cantidad

        # Validar solo stock de producto terminado
        if producto.stock > 0 and total_solicitado > producto.stock:
            return JsonResponse({
                'success': False,
                'error': (
                    f'Stock insuficiente. '
                    f'Solo hay {producto.stock} unidades disponibles '
                    f'de {producto.nombre}.'
                )
            })

        # Obtener precio base por tamaño
        try:
            pt = ProductoTamano.objects.get(producto=producto, tamano=tamano)
        except ProductoTamano.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'El tamaño no está disponible para este producto.'
            })

        # Aplicar promoción si existe
        from django.utils import timezone as tz
        from decimal import Decimal
        hoy   = tz.now().date()
        promo = producto.promociones_aplicadas.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
        ).first()

        precio_base = pt.precio
        if promo:
            if promo.tipo_descuento == 'porcentaje':
                precio_base = precio_base - (
                    precio_base * Decimal(str(promo.valor_descuento)) / 100
                )
            elif promo.tipo_descuento == 'monto_fijo':
                precio_base = max(Decimal('0'), precio_base - promo.valor_descuento)

        sabores         = Sabor.objects.filter(id__in=sabor_ids)
        addons          = Addon.objects.filter(id__in=addon_ids, activo=True)
        extra_addons    = sum(a.precio_extra for a in addons)
        precio_unitario = precio_base + extra_addons

        item, created = CartItem.objects.get_or_create(
            carrito=carrito_obj,
            producto=producto,
            tamano=tamano,
            defaults={'cantidad':cantidad,'precio_unitario': precio_unitario,}
        )
        if not created:
            item.cantidad        += cantidad
            item.precio_unitario  = precio_unitario
            item.save()

        item.sabores.set(sabores)
        item.addons.set(addons)

        return JsonResponse({
            'success': True,
            'message': f'{producto.nombre} agregado al carrito.'
        })

    return JsonResponse({'success': False, 'error': 'Método no permitido'})

    
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
    from django.db.models import Sum

    hoy = timezone.now().date()

    pedidos_hoy = Pedido.objects.filter(
        fecha_pedido__date=hoy
    ).count()

    pedidos_pendientes_count = Pedido.objects.filter(
        estado__in=['pendiente', 'confirmado']
    ).count()

    insumos_bajos = Insumo.objects.filter(
        stock_actual__lte=models.F('stock_minimo')
    ).count()

    total_usuarios = User.objects.count()

    # Ventas del día
    ventas_hoy = Pedido.objects.filter(
        fecha_pedido__date=hoy,
        estado__in=['listo', 'entregado']
    ).aggregate(total=Sum('total'))['total'] or 0

    # Caja abierta — cualquier cajero
    caja_abierta = Caja.objects.filter(
        estado='abierta'
    ).select_related('empleado_cajero').first()

    # Si hay caja abierta, calcular balance
    balance_caja     = None
    total_ingresos   = None
    total_egresos    = None

    if caja_abierta:
        ingresos_qs    = caja_abierta.ingresos.all()
        egresos_qs     = caja_abierta.egresos.all()
        total_ingresos = sum(i.monto for i in ingresos_qs)
        total_egresos  = sum(e.monto for e in egresos_qs)
        balance_caja   = (
            caja_abierta.monto_inicial +
            total_ingresos -
            total_egresos
        )

    # Producciones en proceso
    producciones_proceso = ProduccionLog.objects.filter(
        estado='en_proceso'
    ).count()

    # Últimos pedidos del día
    ultimos_pedidos = Pedido.objects.filter(
        fecha_pedido__date=hoy
    ).select_related('cliente').order_by('-fecha_pedido')[:5]

    context = {
        'pedidos_hoy':           pedidos_hoy,
        'pedidos_pendientes':    pedidos_pendientes_count,
        'insumos_bajos':         insumos_bajos,
        'total_usuarios':        total_usuarios,
        'ventas_hoy':            ventas_hoy,
        'caja_abierta':          caja_abierta,
        'balance_caja':          balance_caja,
        'total_ingresos':        total_ingresos,
        'total_egresos':         total_egresos,
        'producciones_proceso':  producciones_proceso,
        'ultimos_pedidos':       ultimos_pedidos,
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
    productos = Producto.objects.select_related('categoria').prefetch_related('productotamano_set__tamano').all().order_by('categoria__nombre', 'nombre')
    categorias = Categoria.objects.all()
    context = {'productos':  productos,'categorias': categorias,}
    
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
        try:
            producto.delete()
            messages.success(request, f'Producto "{nombre}" eliminado.')
        except Exception:
            messages.error(
                request,
                f'No se puede eliminar "{nombre}" porque tiene pedidos, '
                f'recetas o items de carrito asociados. '
                f'Desactivalo o eliminá primero esas referencias.'
            )
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
        unidad_id = request.POST.get('unidad_medida')
        unidad = get_object_or_404(UnidadMedida, id=unidad_id)

        def limpiar_decimal(valor, default=0):
            try:
                return float(str(valor).replace(',', '.').strip() or default)
            except (ValueError, TypeError):
                return default

        stock_en_unidad = limpiar_decimal(request.POST.get('stock_actual', 0))
        stock_minimo    = limpiar_decimal(request.POST.get('stock_minimo', 0))

        Insumo.objects.create(
            nombre        = request.POST.get('nombre'),
            descripcion   = request.POST.get('descripcion', ''),
            unidad_medida = unidad,
            stock_actual  = stock_en_unidad * float(unidad.factor_conversion),
            stock_minimo  = stock_minimo    * float(unidad.factor_conversion),
            # precio_unitario_promedio se actualiza automáticamente al registrar compras
        )
        messages.success(request, 'Insumo creado exitosamente.')
        return redirect('gestion_insumos')

    return render(request, 'dashboard/admin/insumo_form.html', {
        'unidades': unidades,
        'accion': 'Crear',
        'stock_display': 0,
        'stock_minimo_display': 0,
    })


@admin_required
def editar_insumo(request, insumo_id):
    insumo = get_object_or_404(Insumo, id=insumo_id)
    unidades = UnidadMedida.objects.all()

    if request.method == 'POST':
        unidad_id = request.POST.get('unidad_medida')
        unidad = get_object_or_404(UnidadMedida, id=unidad_id)

        def limpiar_decimal(valor, default=0):
            try:
                return float(str(valor).replace(',', '.').strip() or default)
            except (ValueError, TypeError):
                return default

        stock_en_unidad = limpiar_decimal(request.POST.get('stock_actual', 0))
        stock_minimo    = limpiar_decimal(request.POST.get('stock_minimo', 0))

        insumo.nombre        = request.POST.get('nombre')
        insumo.descripcion   = request.POST.get('descripcion', '')
        insumo.unidad_medida = unidad
        insumo.stock_actual  = stock_en_unidad * float(unidad.factor_conversion)
        insumo.stock_minimo  = stock_minimo    * float(unidad.factor_conversion)
        # precio_unitario_promedio NO se toca aquí, se actualiza en DetalleCompra.save()
        insumo.save()

        messages.success(request, f'Insumo "{insumo.nombre}" actualizado.')
        return redirect('gestion_insumos')

    return render(request, 'dashboard/admin/insumo_form.html', {
        'insumo': insumo,
        'unidades': unidades,
        'accion': 'Editar',
        'stock_display': round(float(insumo.stock_actual) / float(insumo.unidad_medida.factor_conversion), 3),
        'stock_minimo_display': round(float(insumo.stock_minimo) / float(insumo.unidad_medida.factor_conversion), 3),
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
@login_required
def registrar_pedido(request):
    from django.contrib.auth.models import User
    import json

    caja = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    clientes = User.objects.filter(
        profile__rol__nombre='Cliente'
    ).order_by('first_name')

    productos = Producto.objects.filter(
        stock__gt=0
    ).select_related('categoria').prefetch_related(
        'productotamano_set__tamano'
    ).order_by('categoria__nombre', 'nombre')

    # Construir diccionario de productos con sus tamaños y precios
    productos_json = {}
    for prod in productos:
        tamanos_list = []
        for pt in prod.productotamano_set.all():
            if not pt.tamano.solo_produccion and pt.precio > 0:
                tamanos_list.append({
                    'id':         pt.tamano.id,
                    'nombre':     pt.tamano.nombre,
                    'precio':     int(pt.precio),
                    'maxSabores': pt.tamano.max_sabores,
                })
        productos_json[str(prod.id)] = {
            'nombre':    prod.nombre,
            'categoria': prod.categoria.id,
            'tamanos':   tamanos_list,
        }

    # Sabores por categoría
    from collections import defaultdict
    sabores_por_cat = defaultdict(list)
    sabores_qs = Sabor.objects.filter(
        activo=True
    ).select_related(
        'categoria', 'insumo_stock'
    ).prefetch_related('categorias_extra')

    for sabor in sabores_qs:
        disponible = True
        if sabor.insumo_stock:
            disponible = float(sabor.insumo_stock.stock_actual) > 0
        entrada = {
            'id':        sabor.id,
            'nombre':    sabor.nombre,
            'imagen':    sabor.imagen.url if sabor.imagen else None,
            'disponible': disponible,
        }
        if sabor.categoria:
            sabores_por_cat[str(sabor.categoria.id)].append(entrada)
        for cat_extra in sabor.categorias_extra.all():
            sabores_por_cat[str(cat_extra.id)].append(entrada)

    if request.method == 'POST':
        # — guardar pedido —
        cliente_id    = request.POST.get('cliente_id') or None
        tipo_pedido   = request.POST.get('tipo_pedido', 'local')
        observaciones = request.POST.get('observaciones', '')
        producto_ids  = request.POST.getlist('producto_id[]')
        tamano_ids    = request.POST.getlist('tamano_id[]')
        cantidades    = request.POST.getlist('cantidad[]')
        precios       = request.POST.getlist('precio_unitario[]')
        obs_detalles  = request.POST.getlist('obs_detalle[]')

        if not producto_ids:
            messages.error(request, 'Agregá al menos un producto.')
            return redirect('registrar_pedido')

        pedido = Pedido.objects.create(
            cliente_id     = cliente_id,
            tipo_pedido    = tipo_pedido,
            observaciones  = observaciones,
            estado         = 'pendiente',
            empleado_cajero= request.user,
            total          = 0,
        )

        total = 0
        for i, pid in enumerate(producto_ids):
            if not pid:
                continue
            try:
                producto  = Producto.objects.get(id=pid)
                tamano_id = tamano_ids[i] if i < len(tamano_ids) else None
                tamano    = None
                if tamano_id:
                    try:
                        tamano = Tamano.objects.get(id=tamano_id)
                    except Tamano.DoesNotExist:
                        pass
                cantidad = int(cantidades[i]) if i < len(cantidades) else 1
                precio   = int(float(precios[i])) if i < len(precios) else 0
                obs_det  = obs_detalles[i] if i < len(obs_detalles) else ''
                subtotal = cantidad * precio

                detalle = DetallePedido.objects.create(
                    pedido          = pedido,
                    producto        = producto,
                    tamano          = tamano,
                    cantidad        = cantidad,
                    precio_unitario = precio,
                    subtotal        = subtotal,
                    observaciones   = obs_det,
                )

                # Sabores
                sabor_key = f'sabores_producto_{i}'
                sab_ids   = request.POST.get(sabor_key, '')
                if sab_ids:
                    for sid in sab_ids.split(','):
                        sid = sid.strip()
                        if sid:
                            try:
                                detalle.sabores.add(
                                    Sabor.objects.get(id=int(sid))
                                )
                            except Sabor.DoesNotExist:
                                pass

                total += subtotal
            except (Producto.DoesNotExist, ValueError):
                continue

        pedido.total = total
        pedido.save()

        messages.success(
            request,
            f'Pedido #{pedido.id} registrado correctamente.'
        )
        return redirect('detalle_pedido', pedido_id=pedido.id)

    context = {
        'caja':               caja,
        'clientes':           clientes,
        'productos':          productos,
        'productos_json':     json.dumps(productos_json),
        'sabores_json':       json.dumps(dict(sabores_por_cat)),
    }
    return render(
        request,
        'dashboard/empleado/registrar_pedido.html',
        context
    )


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
        nuevo_estado  = request.POST.get('estado')
        estados_validos = [e[0] for e in Pedido.ESTADOS]

        if nuevo_estado in estados_validos:
            estado_anterior = pedido.estado
            pedido.estado   = nuevo_estado
            pedido.save()

            # Al pasar a "en_preparacion" descontar stock de producto terminado
            if nuevo_estado == 'en_preparacion' and estado_anterior != 'en_preparacion':
                sin_stock = []
                for detalle in pedido.detalles.all():
                    producto = detalle.producto
                    if producto.stock >= detalle.cantidad:
                        producto.stock -= detalle.cantidad
                        producto.save()
                    else:
                        sin_stock.append(
                            f'{producto.nombre}: '
                            f'necesitás {detalle.cantidad}, '
                            f'hay {producto.stock}'
                        )

                if sin_stock:
                    # Revertir estado
                    pedido.estado = estado_anterior
                    pedido.save()
                    messages.error(
                        request,
                        f'Stock insuficiente: {" | ".join(sin_stock)}'
                    )
                    return redirect(
                        request.POST.get('next', 'gestion_pedidos')
                    )

    next_url = request.POST.get('next', 'gestion_pedidos')
    return redirect(next_url)

# Vista de despacho
@login_required
def vista_despacho(request):
    pedidos = Pedido.objects.filter(estado__in=['pendiente', 'confirmado', 'en_preparacion']
    ).prefetch_related(
        'detalles__producto',
        'detalles__tamano',
        'detalles__sabores',
        'detalles__addons',
    ).select_related('cliente').order_by('fecha_pedido')

    return render(request, 'dashboard/empleado/despacho.html', {'pedidos': pedidos,})

# Pedidos Online — Cliente
@login_required
def realizar_pedido_online(request):
    carrito_obj = Carrito.objects.filter(user=request.user).first()
    
    if not carrito_obj or not carrito_obj.items.exists():
        messages.error(request, 'Tu carrito está vacío.')
        return redirect('carrito')
    
    caja_abierta = Caja.objects.filter(estado='abierta').first()
    if not caja_abierta:
        messages.error(
            request,
            'No es posible realizar pedidos en este momento. '
            'La heladería no tiene caja abierta.'
        )
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
@login_required
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


@login_required
def gestion_caja(request):
    es_admin = (
        hasattr(request.user, 'profile') and
        request.user.profile.rol and
        request.user.profile.rol.nombre == 'Administrador'
    )

    if es_admin:
        caja_abierta = Caja.objects.filter(estado='abierta').first()
        cajas_anteriores = Caja.objects.filter(
            estado='cerrada'
        ).select_related('empleado_cajero').order_by('-fecha_apertura')[:10]
    else:
        caja_abierta = Caja.objects.filter(
            empleado_cajero=request.user,
            estado='abierta'
        ).first()
        cajas_anteriores = Caja.objects.filter(
            empleado_cajero=request.user,
            estado='cerrada'
        ).order_by('-fecha_apertura')[:5]

    context = {
        'caja':            caja_abierta,
        'cajas_anteriores': cajas_anteriores,
        'es_admin':        es_admin,
    }

    if caja_abierta:
        ingresos = caja_abierta.ingresos.all().order_by('-fecha')
        egresos  = caja_abierta.egresos.all().order_by('-fecha')
        total_ingresos = sum(i.monto for i in ingresos)
        total_egresos  = sum(e.monto for e in egresos)
        balance = caja_abierta.monto_inicial + total_ingresos - total_egresos

        context.update({
            'ingresos':       ingresos,
            'egresos':        egresos,
            'total_ingresos': total_ingresos,
            'total_egresos':  total_egresos,
            'balance':        balance,
        })

    return render(request, 'dashboard/empleado/gestion_caja.html', context)


@login_required
def registrar_ingreso(request):
    caja = Caja.objects.filter(
        empleado_cajero=request.user,
        estado='abierta'
    ).first()

    if not caja:
        messages.error(
            request,
            'No podés registrar un ingreso sin una caja abierta. '
            'Abrí la caja primero.'
        )
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


@login_required
def registrar_egreso(request):
    caja = Caja.objects.filter(
        empleado_cajero=request.user, estado='abierta'
    ).first()

    if not caja:
        messages.error(
            request,
            'No podés registrar un egreso sin una caja abierta. '
            'Abrí la caja primero.'
        )
        return redirect('apertura_caja')

    total_ingresos = sum(i.monto for i in caja.ingresos.all())
    total_egresos = sum(e.monto for e in caja.egresos.all())
    balance_actual = float(caja.monto_inicial) + float(total_ingresos) - float(total_egresos)

    if request.method == 'POST':
        monto = float(request.POST.get('monto', 0))
        motivo = request.POST.get('motivo')
        tipo_egreso = request.POST.get('tipo_egreso', 'gasto_operativo')
        descripcion = request.POST.get('descripcion', '')
        proveedores = Proveedor.objects.all().order_by('nombre')

        if monto > balance_actual:
            messages.error(request, f'Balance insuficiente. Disponible: G. {balance_actual:,.0f}')
            # no hace falta recalcular, balance_actual ya está
        else:
            Egreso.objects.create(caja=caja,responsable=request.user,monto=monto,motivo=motivo,
            tipo_egreso=tipo_egreso,descripcion=descripcion,nro_comprobante=request.POST.get('nro_comprobante', ''),
            proveedor_id=request.POST.get('proveedor_id') or None,)
            
            messages.success(request, f'Egreso de G. {monto:,.0f} registrado.')
            return redirect('gestion_caja')

    return render(request, 'dashboard/empleado/registrar_egreso.html', {
        'caja': caja,
        'tipos': Egreso.TIPOS_EGRESO,
        'balance_actual': balance_actual,
        'proveedores': Proveedor.objects.all().order_by('nombre'),
    })
    
@login_required
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
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin    = request.GET.get('fecha_fin')

    qs = DetallePedido.objects.filter(
        pedido__estado__in=['listo', 'entregado']
    )
    if fecha_inicio:
        qs = qs.filter(pedido__fecha_pedido__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(pedido__fecha_pedido__date__lte=fecha_fin)

    productos_mas = qs.values('producto__nombre').annotate(
        total_vendido=Sum('cantidad'),
        ingresos=Sum('subtotal')
    ).order_by('-total_vendido')[:10]

    productos_menos = qs.values('producto__nombre').annotate(
        total_vendido=Sum('cantidad'),
        ingresos=Sum('subtotal')
    ).order_by('total_vendido')[:10]

    context = {
        'productos_mas':   productos_mas,
        'productos_menos': productos_menos,
        'fecha_inicio':    fecha_inicio,
        'fecha_fin':       fecha_fin,
    }
    return render(request, 'dashboard/admin/reporte_productos.html', context)


@admin_required
def reporte_clientes(request):
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin    = request.GET.get('fecha_fin')

    qs = Pedido.objects.filter(
        estado__in=['listo', 'entregado'],
        cliente__isnull=False
    )
    if fecha_inicio:
        qs = qs.filter(fecha_pedido__date__gte=fecha_inicio)
    if fecha_fin:
        qs = qs.filter(fecha_pedido__date__lte=fecha_fin)

    top_clientes = qs.values(
        'cliente__username',
        'cliente__first_name',
        'cliente__last_name',
    ).annotate(
        total_pedidos=Count('id'),
        total_gastado=Sum('total')
    ).order_by('-total_gastado')[:10]

    context = {
        'top_clientes': top_clientes,
        'fecha_inicio': fecha_inicio,
        'fecha_fin':    fecha_fin,
    }
    return render(request, 'dashboard/admin/reporte_clientes.html', context)


@admin_required
def reporte_costos(request):
    mes  = int(request.GET.get('mes',  timezone.now().month))
    anio = int(request.GET.get('anio', timezone.now().year))

    ventas_mes = Pedido.objects.filter(
        estado__in=['listo', 'entregado'],
        fecha_pedido__month=mes,
        fecha_pedido__year=anio,
    ).aggregate(total=Sum('total'))['total'] or 0

    # Costo real = insumos descontados en producciones completadas ese mes
    # Se calcula multiplicando cantidad_requerida * cantidad_real * precio_unitario_promedio
    costo_produccion = 0
    producciones_mes = ProduccionLog.objects.filter(
        estado='completada',
        fecha_completada__month=mes,
        fecha_completada__year=anio,
    ).select_related('producto')

    for log in producciones_mes:
        recetas = Receta.objects.filter(
            producto=log.producto
        ).select_related('insumo')
        for receta in recetas:
            cantidad_usada  = float(receta.cantidad_requerida) * float(log.cantidad_planificada)
            costo_produccion += (
                cantidad_usada * float(receta.insumo.precio_unitario_promedio)
            )

    # Egresos operativos del mes (sin compras de insumos)
    egresos_operativos = Egreso.objects.filter(
        fecha__month=mes,
        fecha__year=anio,
    ).exclude(
        tipo_egreso='compra_insumos'
    ).aggregate(total=Sum('monto'))['total'] or 0

    ganancia = float(ventas_mes) - costo_produccion - float(egresos_operativos)

    meses = [
        (1,'Enero'),(2,'Febrero'),(3,'Marzo'),(4,'Abril'),
        (5,'Mayo'),(6,'Junio'),(7,'Julio'),(8,'Agosto'),
        (9,'Septiembre'),(10,'Octubre'),(11,'Noviembre'),(12,'Diciembre')
    ]

    context = {
        'ventas_mes':          ventas_mes,
        'costo_produccion':    round(costo_produccion, 0),
        'egresos_operativos':  egresos_operativos,
        'ganancia':            round(ganancia, 0),
        'mes_actual':          mes,
        'anio_actual':         anio,
        'meses':               meses,
        'producciones_mes':    producciones_mes,
    }
    return render(request, 'dashboard/admin/reporte_costos.html', context)

# Ticket de pago
@login_required
def confirmar_pago(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

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
        pedido.metodo_pago      = metodo_pago
        pedido.pago_confirmado  = True
        pedido.estado           = 'entregado'
        pedido.save()

        # Usar get_or_create para evitar duplicados
        Ingreso.objects.get_or_create(
            pedido=pedido,
            defaults={
                'caja':        caja_abierta,
                'monto':       pedido.total,
                'tipo_ingreso': 'venta',
                'descripcion': f'Pedido #{pedido.id} — {metodo_pago}',
            }
        )

        messages.success(request, 'Pago confirmado y registrado en caja.')
        return redirect('ticket_pedido', pedido_id=pedido.id)

    detalles = pedido.detalles.select_related('producto', 'tamano').all()
    return render(request, 'dashboard/empleado/confirmar_pago.html', {
        'pedido':   pedido,
        'detalles': detalles,
        'metodos':  Pedido.METODOS_PAGO,
        'caja':     caja_abierta,
    })
    
@login_required
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
   
# ABM Addons / Agregados
@admin_required
def gestion_addons(request):
    addons  = Addon.objects.select_related('insumo').all().order_by('nombre')
    insumos = Insumo.objects.select_related('unidad_medida').all().order_by('nombre')
    context = {
        'addons':  addons,
        'insumos': insumos,
    }
    return render(request, 'dashboard/admin/addons.html', context)


@admin_required
def crear_addon(request):
    insumos    = Insumo.objects.select_related(
        'unidad_medida'
    ).all().order_by('nombre')
    categorias = Categoria.objects.all().order_by('nombre')

    if request.method == 'POST':
        def limpiar_decimal(valor, default=0):
            try:
                return float(
                    str(valor).replace(',', '.').strip() or default
                )
            except (ValueError, TypeError):
                return default

        insumo_id          = request.POST.get('insumo_id') or None
        cantidad_en_unidad = limpiar_decimal(
            request.POST.get('cantidad_descontar', 0)
        )
        cantidad_base = 0

        if insumo_id:
            insumo        = get_object_or_404(Insumo, id=insumo_id)
            cantidad_base = cantidad_en_unidad * float(
                insumo.unidad_medida.factor_conversion
            )

        addon = Addon(
            nombre             = request.POST.get('nombre'),
            precio_extra       = limpiar_decimal(
                request.POST.get('precio_extra', 0)
            ),
            insumo_id          = insumo_id,
            cantidad_descontar = cantidad_base,
            activo             = request.POST.get('activo') == 'on',
        )
        addon.save()

        # Guardar categorías DESPUÉS del save para que exista el ID
        cat_ids = request.POST.getlist('categorias[]')
        if cat_ids:
            addon.categorias.set(cat_ids)
        else:
            addon.categorias.clear()

        messages.success(
            request, f'Agregado "{addon.nombre}" creado exitosamente.'
        )
        return redirect('gestion_addons')

    return render(request, 'dashboard/admin/addon_form.html', {
        'insumos':                insumos,
        'categorias':             categorias,
        'categorias_seleccionadas': [],
        'accion':                 'Crear',
    })


@admin_required
def editar_addon(request, addon_id):
    addon      = get_object_or_404(Addon, id=addon_id)
    insumos    = Insumo.objects.select_related(
        'unidad_medida'
    ).all().order_by('nombre')
    categorias = Categoria.objects.all().order_by('nombre')

    if request.method == 'POST':
        def limpiar_decimal(valor, default=0):
            try:
                return float(
                    str(valor).replace(',', '.').strip() or default
                )
            except (ValueError, TypeError):
                return default

        insumo_id          = request.POST.get('insumo_id') or None
        cantidad_en_unidad = limpiar_decimal(
            request.POST.get('cantidad_descontar', 0)
        )
        cantidad_base = 0

        if insumo_id:
            insumo        = get_object_or_404(Insumo, id=insumo_id)
            cantidad_base = cantidad_en_unidad * float(
                insumo.unidad_medida.factor_conversion
            )

        addon.nombre             = request.POST.get('nombre')
        addon.precio_extra       = limpiar_decimal(
            request.POST.get('precio_extra', 0)
        )
        addon.insumo_id          = insumo_id
        addon.cantidad_descontar = cantidad_base
        addon.activo             = request.POST.get('activo') == 'on'
        addon.save()

        cat_ids = request.POST.getlist('categorias[]')
        if cat_ids:
            addon.categorias.set(cat_ids)
        else:
            addon.categorias.clear()

        messages.success(
            request, f'Agregado "{addon.nombre}" actualizado.'
        )
        return redirect('gestion_addons')

    cantidad_display = 0
    if addon.insumo and addon.cantidad_descontar:
        cantidad_display = round(
            float(addon.cantidad_descontar) /
            float(addon.insumo.unidad_medida.factor_conversion), 4
        )

    return render(request, 'dashboard/admin/addon_form.html', {
        'addon':                  addon,
        'insumos':                insumos,
        'categorias':             categorias,
        'categorias_seleccionadas': list(
            addon.categorias.values_list('id', flat=True)
        ),
        'accion':                 'Editar',
        'cantidad_display':       cantidad_display,
    })


@admin_required
def eliminar_addon(request, addon_id):
    addon = get_object_or_404(Addon, id=addon_id)
    if request.method == 'POST':
        nombre = addon.nombre
        addon.delete()
        messages.success(request, f'Agregado "{nombre}" eliminado.')
    return redirect('gestion_addons')   
    
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
        insumo_id   = request.POST.get('insumo')

        def limpiar_decimal(valor, default=0):
            try:
                return float(str(valor).replace(',', '.').strip() or default)
            except (ValueError, TypeError):
                return default

        cantidad_en_unidad = limpiar_decimal(request.POST.get('cantidad_requerida', 0))

        insumo = get_object_or_404(Insumo, id=insumo_id)
        # Convertir a unidad base (gramos/mL) para guardar
        cantidad_base = cantidad_en_unidad * float(insumo.unidad_medida.factor_conversion)

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
                cantidad_requerida=cantidad_base,
            )
            messages.success(request, 'Receta creada exitosamente.')
        return redirect('gestion_recetas')

    productos = Producto.objects.all().order_by('nombre')
    insumos   = Insumo.objects.select_related('unidad_medida').all().order_by('nombre')
    return render(request, 'dashboard/admin/receta_form.html', {
        'productos': productos,
        'insumos':   insumos,
        'accion':    'Crear',
    })


@admin_required
def editar_receta(request, receta_id):
    receta  = get_object_or_404(Receta, id=receta_id)
    productos = Producto.objects.all().order_by('nombre')
    insumos   = Insumo.objects.select_related('unidad_medida').all().order_by('nombre')

    if request.method == 'POST':
        insumo_id = request.POST.get('insumo')
        insumo    = get_object_or_404(Insumo, id=insumo_id)

        def limpiar_decimal(valor, default=0):
            try:
                return float(str(valor).replace(',', '.').strip() or default)
            except (ValueError, TypeError):
                return default

        cantidad_en_unidad = limpiar_decimal(request.POST.get('cantidad_requerida', 0))
        cantidad_base = cantidad_en_unidad * float(insumo.unidad_medida.factor_conversion)

        receta.producto_id        = request.POST.get('producto')
        receta.insumo_id          = insumo_id
        receta.cantidad_requerida = cantidad_base
        receta.save()
        messages.success(request, 'Receta actualizada.')
        return redirect('gestion_recetas')

    # Convertir cantidad guardada a unidad legible para mostrar en el form
    cantidad_display = round(
        float(receta.cantidad_requerida) /
        float(receta.insumo.unidad_medida.factor_conversion), 4
    )

    return render(request, 'dashboard/admin/receta_form.html', {
        'receta':            receta,
        'productos':         productos,
        'insumos':           insumos,
        'accion':            'Editar',
        'cantidad_display':  cantidad_display,
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
        producto_id     = request.POST.get('producto')
        observaciones   = request.POST.get('observaciones', '')

        def limpiar_decimal(valor, default=0):
            try:
                return float(str(valor).replace(',', '.').strip() or default)
            except (ValueError, TypeError):
                return default

        try:
            cantidad_planif = int(request.POST.get('cantidad_producida', 0))
        except (ValueError, TypeError):
            cantidad_planif = 0

        if cantidad_planif <= 0:
            messages.error(request, 'La cantidad debe ser mayor a 0.')
            return redirect('registrar_produccion')

        producto = get_object_or_404(Producto, id=producto_id)
        recetas  = Receta.objects.filter(
            producto=producto
        ).select_related('insumo__unidad_medida')

        if not recetas.exists():
            messages.error(
                request,
                f'"{producto.nombre}" no tiene receta cargada. '
                f'Cargá la receta antes de registrar producción.'
            )
            return redirect('registrar_produccion')

        # Verificar stock suficiente antes de descontar
        insumos_faltantes = []
        for receta in recetas:
            insumo    = receta.insumo
            necesario = float(receta.cantidad_requerida) * cantidad_planif
            if float(insumo.stock_actual) < necesario:
                necesario_display  = round(
                    necesario / float(insumo.unidad_medida.factor_conversion), 3
                )
                disponible_display = round(
                    float(insumo.stock_actual) / float(insumo.unidad_medida.factor_conversion), 3
                )
                insumos_faltantes.append(
                    f'{insumo.nombre}: necesitás {necesario_display} '
                    f'{insumo.unidad_medida.simbolo}, '
                    f'hay {disponible_display} {insumo.unidad_medida.simbolo}'
                )

        if insumos_faltantes:
            messages.error(
                request,
                f'Insumos insuficientes: {" | ".join(insumos_faltantes)}'
            )
            return redirect('registrar_produccion')

        # Descontar insumos
        for receta in recetas:
            insumo             = receta.insumo
            cantidad_descontar = float(receta.cantidad_requerida) * cantidad_planif
            insumo.stock_actual = float(insumo.stock_actual) - cantidad_descontar
            cantidad_display   = round(
                cantidad_descontar / float(insumo.unidad_medida.factor_conversion), 3
            )
            nombre_corto = producto.nombre[:25]
            insumo.ultima_operacion = (
                f'Prod: -{cantidad_display}{insumo.unidad_medida.simbolo} '
                f'({nombre_corto})'
            )
            insumo.save()

        # Crear log en estado "en_proceso" — stock del producto NO se toca aún
        ProduccionLog.objects.create(
            producto             = producto,
            cantidad_planificada = cantidad_planif,
            responsable          = request.user,
            observaciones        = observaciones,
            estado               = 'en_proceso',
        )

        messages.success(
            request,
            f'✅ Producción iniciada: {cantidad_planif} unidades de '
            f'"{producto.nombre}". Insumos descontados. '
            f'Cuando esté lista, registrá la cantidad real en el historial.'
        )
        return redirect('historial_produccion')

    # Calcular producible por producto
    productos_con_info = []
    for producto in productos:
        recetas = producto.recetas.all()
        if recetas:
            min_producible = None
            limitante      = None
            detalle_receta = []
            for receta in recetas:
                insumo = receta.insumo
                if float(receta.cantidad_requerida) > 0:
                    producible = int(
                        float(insumo.stock_actual) / float(receta.cantidad_requerida)
                    )
                    if min_producible is None or producible < min_producible:
                        min_producible = producible
                        limitante      = insumo.nombre
                stock_display    = round(
                    float(insumo.stock_actual) /
                    float(insumo.unidad_medida.factor_conversion), 3
                )
                cantidad_display = round(
                    float(receta.cantidad_requerida) /
                    float(insumo.unidad_medida.factor_conversion), 4
                )
                detalle_receta.append({
                    'insumo':   insumo.nombre,
                    'cantidad': cantidad_display,
                    'unidad':   insumo.unidad_medida.simbolo,
                    'stock':    stock_display,
                })
            productos_con_info.append({
                'producto':   producto,
                'producible': min_producible or 0,
                'limitante':  limitante,
                'receta':     detalle_receta,
            })
        else:
            productos_con_info.append({
                'producto':   producto,
                'producible': None,
                'limitante':  None,
                'receta':     [],
            })

    logs_en_proceso = ProduccionLog.objects.filter(
        estado='en_proceso'
    ).select_related('producto', 'responsable').order_by('-fecha')

    return render(request, 'dashboard/admin/registrar_produccion.html', {
        'productos_con_info': productos_con_info,
        'logs_en_proceso':    logs_en_proceso,
    })


@admin_required
def editar_produccion(request, log_id):
    log = get_object_or_404(ProduccionLog, id=log_id)

    if log.estado == 'completada':
        messages.error(request, 'No podés editar una producción ya completada.')
        return redirect('registrar_produccion')

    if request.method == 'POST':
        def limpiar_decimal(valor, default=0):
            try:
                return float(str(valor).replace(',', '.').strip() or default)
            except (ValueError, TypeError):
                return default

        nueva_cantidad = limpiar_decimal(
            request.POST.get('cantidad_planificada', 0)
        )
        observaciones = request.POST.get('observaciones', '')

        if nueva_cantidad <= 0:
            messages.error(request, 'La cantidad debe ser mayor a 0.')
            return redirect('registrar_produccion')

        cantidad_anterior = float(log.cantidad_planificada)
        diferencia        = nueva_cantidad - cantidad_anterior

        if diferencia != 0:
            # Ajustar insumos según la diferencia
            recetas = Receta.objects.filter(
                producto=log.producto
            ).select_related('insumo__unidad_medida')

            if diferencia > 0:
                # Necesita más insumos — verificar stock
                faltantes = []
                for receta in recetas:
                    insumo    = receta.insumo
                    necesario = float(receta.cantidad_requerida) * diferencia
                    if float(insumo.stock_actual) < necesario:
                        disp = round(
                            float(insumo.stock_actual) /
                            float(insumo.unidad_medida.factor_conversion), 3
                        )
                        faltantes.append(
                            f'{insumo.nombre}: hay {disp} '
                            f'{insumo.unidad_medida.simbolo}'
                        )
                if faltantes:
                    messages.error(
                        request,
                        f'Stock insuficiente para ampliar: {" | ".join(faltantes)}'
                    )
                    return redirect('registrar_produccion')

            for receta in recetas:
                insumo          = receta.insumo
                ajuste          = float(receta.cantidad_requerida) * diferencia
                insumo.stock_actual = float(insumo.stock_actual) - ajuste
                ajuste_display  = round(
                    abs(ajuste) / float(insumo.unidad_medida.factor_conversion), 3
                )
                signo = '-' if ajuste > 0 else '+'
                nombre_corto = log.producto.nombre[:20]
                insumo.ultima_operacion = (
                    f'Ajuste prod: {signo}{ajuste_display}'
                    f'{insumo.unidad_medida.simbolo} ({nombre_corto})'
                )
                insumo.save()

        log.cantidad_planificada = nueva_cantidad
        log.observaciones        = observaciones
        log.save()

        messages.success(
            request,
            f'Producción actualizada: {nueva_cantidad} unidades de '
            f'"{log.producto.nombre}".'
        )
        return redirect('registrar_produccion')

    return redirect('registrar_produccion')

@admin_required
def completar_produccion(request, log_id):
    log = get_object_or_404(ProduccionLog, id=log_id)

    if log.estado == 'completada':
        messages.error(request, 'Esta producción ya fue completada.')
        return redirect('registrar_produccion')

    if request.method == 'POST':
        def limpiar_decimal(valor, default=0):
            try:
                return float(str(valor).replace(',', '.').strip() or default)
            except (ValueError, TypeError):
                return default

        cantidad_real = limpiar_decimal(request.POST.get('cantidad_real', 0))

        if cantidad_real <= 0:
            messages.error(
                request, 'La cantidad real debe ser mayor a 0.'
            )
            return redirect('registrar_produccion')

        producto       = log.producto
        stock_anterior = float(producto.stock)
        producto.stock = stock_anterior + cantidad_real
        producto.save()

        from decimal import Decimal
        log.cantidad_real    = Decimal(str(cantidad_real))
        log.estado           = 'completada'
        log.fecha_completada = timezone.now()
        log.save()

        messages.success(
            request,
            f'✅ Producción completada: {cantidad_real} unidades de '
            f'"{producto.nombre}" agregadas al stock. '
            f'Stock: {stock_anterior} → {producto.stock}.'
        )
    return redirect('registrar_produccion')

@admin_required
def historial_produccion(request):
    producto_id  = request.GET.get('producto_id')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin    = request.GET.get('fecha_fin')
    estado_filtro = request.GET.get('estado', '')

    logs = ProduccionLog.objects.select_related(
        'producto__categoria', 'responsable'
    ).all()

    if producto_id:
        logs = logs.filter(producto_id=producto_id)
    if fecha_inicio:
        logs = logs.filter(fecha__date__gte=fecha_inicio)
    if fecha_fin:
        logs = logs.filter(fecha__date__lte=fecha_fin)
    if estado_filtro:
        logs = logs.filter(estado=estado_filtro)

    # POST — confirmar cantidad real
    if request.method == 'POST':
        log_id = request.POST.get('log_id')
        log    = get_object_or_404(ProduccionLog, id=log_id)

        if log.estado == 'completada':
            messages.error(request, 'Esta producción ya fue completada.')
            return redirect('historial_produccion')

        try:
            from decimal import Decimal
            cantidad_real = Decimal(
                str(request.POST.get('cantidad_real', 0)).replace(',', '.')
            )
            if cantidad_real <= 0:
                raise ValueError
        except Exception:
            messages.error(
                request,
                'La cantidad real debe ser un número mayor a 0.'
            )
            return redirect('historial_produccion')

        # Sumar al stock del producto terminado
        producto = log.producto
        stock_anterior   = producto.stock
        producto.stock   = float(producto.stock) + float(cantidad_real)
        producto.save()

        log.cantidad_real    = cantidad_real
        log.estado           = 'completada'
        log.fecha_completada = timezone.now()
        log.save()

        messages.success(
            request,
            f'✅ Producción completada: {cantidad_real} unidades de '
            f'"{producto.nombre}" sumadas al stock. '
            f'Stock: {stock_anterior} → {producto.stock}.'
        )
        return redirect('historial_produccion')

    productos = Producto.objects.all().order_by('nombre')

    # Totales del historial filtrado
    total_planificado = sum(
        float(l.cantidad_planificada) for l in logs
    )
    total_real = sum(
        float(l.cantidad_real) for l in logs if l.cantidad_real
    )

    context = {
        'logs':             logs,
        'productos':        productos,
        'producto_id':      producto_id,
        'fecha_inicio':     fecha_inicio,
        'fecha_fin':        fecha_fin,
        'estado_filtro':    estado_filtro,
        'total_planificado': total_planificado,
        'total_real':        total_real,
    }
    return render(request, 'dashboard/admin/historial_produccion.html', context)