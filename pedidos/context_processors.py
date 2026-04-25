from .models import Insumo
from django.db.models import F

def alertas_stock(request):
    """
    Inyecta automáticamente las alertas de stock bajo
    en todos los templates del sistema.
    """
    alertas = []
    if request.user.is_authenticated:
        try:
            rol = request.user.profile.rol.nombre
            if rol in ['Administrador', 'Empleado']:
                alertas = Insumo.objects.filter(
                    stock_actual__lte=F('stock_minimo')
                ).values('nombre', 'stock_actual', 'stock_minimo')
        except AttributeError:
            pass
    return {
        'alertas_stock': alertas,
        'alertas_count': len(alertas),
    }