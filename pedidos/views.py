from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from decimal import Decimal

from .forms import SignUpForm
from .models import (
    Sabor, Addon, Carrito, CartItem, Categoria,
    Producto, Tamano, ProductoTamano)

# ==============================
# Vistas de autenticación
# ==============================

def registro_view(request):  # antes signup_view
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'registro.html', {'form': form})  # antes signup.html

def login_view(request):
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password')
        )
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Usuario o contraseña incorrectos')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# ==============================
# Vistas de categorías y productos
# ==============================

@method_decorator(login_required, name='dispatch')
class CategoriaListView(ListView):
    model = Categoria
    template_name = 'categorias/lista.html'
    context_object_name = 'categorias'

@login_required
def dashboard(request):  # antes menu
    categorias = Categoria.objects.all()
    return render(request, 'dashboard.html', {'categorias': categorias})  # antes menu.html

@login_required
def productos_categoria(request, categoria_slug):  # antes categoria_detalle
    categoria = get_object_or_404(Categoria, slug=categoria_slug)
    productos = Producto.objects.filter(categoria=categoria, disponible=True)
    tamanos = Tamano.objects.filter(activo=True)
    sabores = Sabor.objects.filter(categorias=categoria, activo=True)

    productos_con_precios = []
    for producto in productos:
        precios = ProductoTamano.objects.filter(producto=producto).select_related('tamano')
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
    return render(request, 'productos_categoria.html', context)  # antes categoria_detalle.html

# ==============================
# Vistas del carrito
# ==============================

@login_required
def agregar_carrito(request):  # antes add_to_cart
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        tamano_id = request.POST.get('tamano_id')
        sabor_ids = request.POST.getlist('sabor_ids')
        cantidad = int(request.POST.get('cantidad', 1))

        producto = get_object_or_404(Producto, id=producto_id, disponible=True)
        tamano = get_object_or_404(Tamano, id=tamano_id, activo=True)

        try:
            pt = ProductoTamano.objects.get(producto=producto, tamano=tamano)
            precio_base = pt.precio
        except ProductoTamano.DoesNotExist:
            messages.error(request, 'El tamaño seleccionado no está disponible para este producto.')
            return redirect('productos_categoria', categoria_slug=producto.categoria.slug)

        sabores = Sabor.objects.filter(id__in=sabor_ids)
        extra_sabores = sum(s.precio_extra for s in sabores)

        precio_unitario = precio_base + extra_sabores

        cart, _ = Carrito.objects.get_or_create(user=request.user)

        item = CartItem.objects.create(
            cart=cart,
            producto=producto,
            tamano=tamano,
            cantidad=cantidad,
            precio_unitario=precio_unitario
        )
        item.sabores.set(sabores)

        messages.success(request, 'Producto agregado al carrito.')
        return redirect('productos_categoria', categoria_slug=producto.categoria.slug)

    return redirect('dashboard')

@login_required
def carrito(request):  # antes view_cart
    cart, _ = Carrito.objects.get_or_create(user=request.user)
    items = cart.items.all()

    total = Decimal('0')
    for item in items:
        item.subtotal = item.precio_unitario * item.cantidad
        total += item.subtotal

    context = {
        'items': items,
        'total': total,
    }
    return render(request, 'carrito.html', context)  # antes cart.html