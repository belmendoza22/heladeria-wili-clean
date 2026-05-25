from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Modelos del menú
class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    imagen = models.ImageField(upload_to='images/Categorias/', blank=True, null=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.nombre

class Subcategoria(models.Model):
    nombre    = models.CharField(max_length=100)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name='subcategorias'
    )
    activo    = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f'{self.categoria.nombre} — {self.nombre}'

class Sabor(models.Model):
    nombre = models.CharField(max_length=100)
    precio_extra = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    descripcion = models.TextField(blank=True)
    imagen = models.ImageField(upload_to='images/Sabores/', blank=True, null=True)
    categoria = models.ForeignKey(Categoria,on_delete=models.SET_NULL,null=True,blank=True,related_name='sabores')
    categorias_extra = models.ManyToManyField(Categoria,blank=True,related_name='sabores_extra',help_text='sabores')
    subcategoria = models.ForeignKey('Subcategoria',on_delete=models.SET_NULL,null=True,blank=True,related_name='sabores')
    slug = models.SlugField(unique=True)
    activo = models.BooleanField(default=True)
    gramos_por_porcion = models.DecimalField(max_digits=8, decimal_places=2, default=0,
        help_text='Gramos que se descuentan por porción al pedir este sabor. '
                  'Se puede sobreescribir por categoría de tamaño.')
    insumo_stock = models.ForeignKey('Insumo',on_delete=models.SET_NULL,null=True, blank=True,
        related_name='sabores_asociados',help_text='Insumo de producción que representa este sabor '
                  '(para verificar disponibilidad)')

    def __str__(self):
        return self.nombre



class Addon(models.Model):
    nombre = models.CharField(max_length=100)
    precio_extra = models.DecimalField(
        max_digits=10, decimal_places=0, default=0,
        help_text='Costo extra para el cliente (puede ser 0)'
    )
    insumo = models.ForeignKey(
        'Insumo',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='addons',
        help_text='Insumo que se descuenta al elegir este agregado'
    )
    categorias = models.ManyToManyField('Categoria',blank=True,related_name='addons',help_text='Categorías donde se muestra este agregado. '
                                        'Si no seleccionás ninguna, aparece en todas.')
    cantidad_descontar = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        help_text='Cantidad a descontar del insumo (en unidad base, ej: gramos)'
    )
    activo = models.BooleanField(default=True)
    imagen = models.ImageField(upload_to='images/Addons/', blank=True, null=True)

    def __str__(self):
        return self.nombre


class Tamano(models.Model):
    nombre = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    categoria = models.ForeignKey(Categoria,on_delete=models.SET_NULL,null=True,blank=True)
    precio_extra = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    max_sabores = models.PositiveIntegerField(default=1,
        help_text='Cantidad máxima de sabores que puede elegir el cliente')
    solo_produccion = models.BooleanField(default=False,
        help_text='Si está marcado, este tamaño no se muestra a clientes')
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name='productos'
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    precio_base = models.DecimalField(max_digits=10, decimal_places=0, default=0, blank=True)
    stock = models.IntegerField(default=0)
    imagen = models.ImageField(upload_to='images/Productos/', blank=True, null=True)
    destacado = models.BooleanField(default=False, help_text="Marcar para mostrar en la página principal como destacado")

    def __str__(self):
        return self.nombre


class ProductoTamano(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, null=True)
    tamano = models.ForeignKey(Tamano, on_delete=models.CASCADE, null=True)
    precio = models.DecimalField(max_digits=10, decimal_places=0)

    class Meta:
        unique_together = ('producto', 'tamano')

    def __str__(self):
        return f"{self.producto} - {self.tamano} : ${self.precio}"


# Modelos del carrito
class Carrito(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Carrito de {self.user.username}"


class CartItem(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, null=True)
    tamano = models.ForeignKey(Tamano, on_delete=models.CASCADE, null=True)
    sabores = models.ManyToManyField(Sabor, blank=True)
    addons = models.ManyToManyField(Addon, blank=True)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=0)

    def __str__(self):
        tamano_str = self.tamano.nombre if self.tamano else 'sin tamaño'
        return f"{self.cantidad} x {self.producto.nombre} ({tamano_str})"


# Modelos de perfil de usuario
class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class Permiso(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)

    def __str__(self):
        return self.nombre

class RolPermiso(models.Model):
    rol = models.ForeignKey(Rol, on_delete=models.CASCADE)
    permiso = models.ForeignKey(Permiso, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('rol', 'permiso')
        
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Teléfono', max_length=20, blank=True)
    address = models.CharField('Dirección', max_length=255, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'Perfil de {self.user.username}'
    
# Modelos de Stock e Insumos
class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    simbolo = models.CharField(max_length=10)
    # Factor para convertir a unidad base (gramos o mililitros)
    # Ej: kg = 1000, g = 1, L = 1000, mL = 1
    factor_conversion = models.DecimalField(
        max_digits=10, decimal_places=2, default=1,
        help_text='Factor para convertir a unidad base. Ej: kg=1000, g=1, L=1000'
    )

    def __str__(self):
        return f"{self.nombre} ({self.simbolo})"


class Insumo(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT)
    stock_actual = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    precio_unitario_promedio = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    ultima_operacion = models.CharField(max_length=200, blank=True, default='')

    def stock_en_unidad_display(self):
        """Retorna el stock convertido a la unidad de medida"""
        return self.stock_actual / self.unidad_medida.factor_conversion

    def convertir_a_base(self, cantidad_en_unidad):
        """Convierte cantidad en la unidad del insumo a unidad base"""
        return cantidad_en_unidad * self.unidad_medida.factor_conversion

    def convertir_de_base(self, cantidad_base):
        """Convierte de unidad base a la unidad del insumo"""
        return cantidad_base / self.unidad_medida.factor_conversion
    
    @property
    def stock_display(self):
        """Stock en la unidad legible (ej: kg en vez de gramos)"""
        if self.unidad_medida.factor_conversion:
            return round(self.stock_actual / self.unidad_medida.factor_conversion, 2)
        return self.stock_actual

    @property
    def stock_minimo_display(self):
        """Stock mínimo en la unidad legible"""
        if self.unidad_medida.factor_conversion:
            return round(self.stock_minimo / self.unidad_medida.factor_conversion, 2)
        return self.stock_minimo
    
    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ruc = models.CharField(max_length=20, unique=True)
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.nombre


class Receta(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='recetas')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT)
    cantidad_requerida = models.DecimalField(max_digits=10, decimal_places=4)

    class Meta:
        unique_together = ('producto', 'insumo')

    def __str__(self):
        cantidad_display = round(
            self.cantidad_requerida / self.insumo.unidad_medida.factor_conversion, 4
        )
        return (
            f"{self.producto.nombre} necesita "
            f"{cantidad_display} {self.insumo.unidad_medida.simbolo} "
            f"de {self.insumo.nombre}"
        )


# Modelos de Compras
class Compra(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT)
    empleado = models.ForeignKey(User, on_delete=models.PROTECT, related_name='compras_realizadas')
    total_compra = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    def __str__(self):
        return f"Compra #{self.id} - {self.proveedor.nombre} - {self.fecha.date()}"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='detalles')
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=3)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from decimal import Decimal
        insumo = self.insumo
        cantidad_base  = Decimal(str(self.cantidad)) * insumo.unidad_medida.factor_conversion
        stock_anterior = Decimal(str(insumo.stock_actual))
        precio_anterior = Decimal(str(insumo.precio_unitario_promedio))
        nuevo_stock    = stock_anterior + cantidad_base

        if nuevo_stock > 0:
            insumo.precio_unitario_promedio = (
                (stock_anterior * precio_anterior) +
                (cantidad_base  * Decimal(str(self.precio_unitario)))
            ) / nuevo_stock

        insumo.stock_actual     = nuevo_stock
        insumo.ultima_operacion = (
            f'Compra: +{self.cantidad} {insumo.unidad_medida.simbolo}'
        )
        insumo.save()

    def __str__(self):
        return f"{self.cantidad} {self.insumo.unidad_medida.simbolo} de {self.insumo.nombre}"


# Modelos de Pedidos
class Pedido(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('en_preparacion', 'En preparación'),
        ('listo', 'Listo para retirar'),
        ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ]
    TIPOS = [
        ('local', 'En local'),
        ('online', 'Online (pick-up)'),
    ]
    METODOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia bancaria'),
    ]
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO,
        default='efectivo',
        blank=True
    )
    pago_confirmado = models.BooleanField(default=False)
    cliente = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pedidos', null=True, blank=True)
    empleado_cajero = models.ForeignKey(User, on_delete=models.PROTECT, related_name='pedidos_registrados', null=True, blank=True)
    fecha_pedido = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    tipo_pedido = models.CharField(max_length=20, choices=TIPOS, default='local')
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"Pedido #{self.id} - {self.get_estado_display()}"

    def calcular_total(self):
        total = sum(detalle.subtotal for detalle in self.detalles.all())
        self.total = total
        self.save()
        return total


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    tamano = models.ForeignKey(Tamano, on_delete=models.PROTECT, null=True, blank=True)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=0, editable=False)
    sabores = models.ManyToManyField(Sabor, blank=True)
    addons = models.ManyToManyField(Addon, blank=True)
    observaciones = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.subtotal = self.precio_unitario * self.cantidad
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"


# Modelos de Caja
class Caja(models.Model):
    ESTADOS_CAJA = [
        ('abierta', 'Abierta'),
        ('cerrada', 'Cerrada'),
    ]
    empleado_cajero = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cajas')
    fecha_apertura = models.DateTimeField(auto_now_add=True)
    monto_inicial = models.DecimalField(max_digits=12, decimal_places=0)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    monto_final_sistema = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    monto_final_contado = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS_CAJA, default='abierta')

    def __str__(self):
        return f"Caja #{self.id} ({self.estado}) - {self.fecha_apertura.date()}"

    def cerrar(self, monto_contado):
        self.fecha_cierre = timezone.now()
        self.monto_final_contado = monto_contado
        total_ingresos = self.ingresos.aggregate(total=models.Sum('monto'))['total'] or 0
        total_egresos = self.egresos.aggregate(total=models.Sum('monto'))['total'] or 0
        self.monto_final_sistema = self.monto_inicial + total_ingresos - total_egresos
        self.estado = 'cerrada'
        self.save()


class Ingreso(models.Model):
    TIPOS_INGRESO = [
        ('venta', 'Venta'),
        ('otro', 'Otro'),
    ]
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, related_name='ingresos')
    pedido = models.OneToOneField(Pedido, on_delete=models.SET_NULL, null=True, blank=True, related_name='ingreso')
    monto = models.DecimalField(max_digits=12, decimal_places=0)
    tipo_ingreso = models.CharField(max_length=50, choices=TIPOS_INGRESO, default='venta')
    descripcion = models.CharField(max_length=150, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ingreso ${self.monto} - {self.tipo_ingreso}"


class Egreso(models.Model):
    TIPOS_EGRESO = [
        ('compra_insumos', 'Compra de insumos'),
        ('gasto_operativo', 'Gasto operativo'),
        ('otro', 'Otro'),
    ]
    caja = models.ForeignKey(Caja, on_delete=models.CASCADE, related_name='egresos')
    responsable = models.ForeignKey(User, on_delete=models.PROTECT, related_name='egresos_registrados')
    monto = models.DecimalField(max_digits=12, decimal_places=0)
    motivo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    tipo_egreso = models.CharField(max_length=20, choices=TIPOS_EGRESO, default='gasto_operativo')
    nro_comprobante = models.CharField(max_length=50, blank=True, default='',help_text='Número de factura o comprobante')
    proveedor = models.ForeignKey(Proveedor,on_delete=models.SET_NULL,null=True, blank=True,related_name='egresos',help_text='Proveedor asociado al egreso (opcional)')

    def __str__(self):
        return f"Egreso ${self.monto} - {self.motivo}"


# Modelos de Promociones
class Promocion(models.Model):
    TIPO_DESCUENTO = [
        ('porcentaje', 'Porcentaje'),
        ('monto_fijo', 'Monto fijo'),
    ]
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    tipo_descuento = models.CharField(max_length=20, choices=TIPO_DESCUENTO, default='porcentaje')
    valor_descuento = models.DecimalField(max_digits=10, decimal_places=0)
    productos = models.ManyToManyField(Producto, blank=True, related_name='promociones_aplicadas')
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

# Modelo de registro de producción
class ProduccionLog(models.Model):
    ESTADOS = [
        ('en_proceso', 'En proceso'),
        ('completada', 'Completada'),
    ]
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='producciones'
    )
    cantidad_planificada = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text='Cantidad que se planificó producir'
    )
    cantidad_real = models.DecimalField(
        max_digits=10, decimal_places=3,
        null=True, blank=True,
        help_text='Cantidad real que salió de la producción'
    )
    responsable = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='producciones_registradas'
    )
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_completada = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default='en_proceso'
    )

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return (
            f"Producción de {self.cantidad_planificada} x "
            f"{self.producto.nombre} — {self.fecha.strftime('%d/%m/%Y %H:%M')}"
        )