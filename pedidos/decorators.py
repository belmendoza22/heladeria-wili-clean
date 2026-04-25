from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from .models import (
    Sabor, Addon, Carrito, CartItem, Categoria,
    Producto, Tamano, ProductoTamano, Rol, Permiso, 
    RolPermiso, Profile, UnidadMedida, Insumo,
    Proveedor, Receta, Compra, DetalleCompra, Pedido)

def rol_requerido(allowed_roles=[]):
    """
    Decorador para restringir acceso según roles.
    roles_permitidos puede ser un string con un rol o una lista de roles.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Debes iniciar sesión para acceder.')
                return redirect('login')
            # Obtener el perfil y el rol
            try:
                user_role = request.user.profile.rol.nombre  # Asumiendo que Profile tiene un FK a Rol con campo 'nombre'
            except AttributeError:
                messages.error(request, 'No tienes un perfil asignado.')
                return redirect('menu')
                
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, 'No tienes permiso para acceder a esta página.')
                return redirect('menu')
        return _wrapped_view
    return decorator

# Decoradores específicos (opcional)
def admin_required(view_func):
    return rol_requerido(['Administrador'])(view_func)

def empleado_required(view_func):
    return rol_requerido(['Administrador', 'Empleado'])(view_func)