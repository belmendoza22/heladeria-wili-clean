from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django.urls import reverse

# ==============================
# Modelos del menú
# ==============================

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    imagen = models.ImageField(upload_to='categorias/', blank=True, null=True)
    slug = models.SlugField(unique=True)

    #class Meta:
    #    verbose_name = "Categoría"
    #   verbose_name_plural = "Categorías"

    def __str__(self):
        return self.nombre

    #def get_absolute_url(self):
    #    return reverse('categoria_detalle', args=[self.slug])

class Sabor(models.Model):
    nombre = models.CharField(max_length=100)
    precio_extra = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    descripcion = models.TextField(blank=True)
    imagen = models.ImageField(upload_to='sabores/', blank=True, null=True)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sabores'
    )
    slug = models.SlugField(unique=True)
    activo = models.BooleanField(default=True)  # Para disponibilidad

    def __str__(self):
        return self.nombre

class Addon(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

class Tamano(models.Model):
    nombre = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    precio_extra = models.DecimalField(max_digits=6, decimal_places=2, default=0)
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
    precio_base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True)
    #disponible = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class ProductoTamano(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, null=True)
    tamano = models.ForeignKey(Tamano, on_delete=models.CASCADE, null=True)
    precio = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        unique_together = ('producto', 'tamano') 

    def __str__(self):
        return f"{self.producto} - {self.tamano} : ${self.precio}"

# ==============================
# Modelos del carrito
# ==============================

class Carrito(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Carrito de {self.user.username}"

class CartItem(models.Model):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, null=True)          # Producto seleccionado
    tamano = models.ForeignKey(Tamano, on_delete=models.CASCADE, null=True)              # Tamaño elegido
    sabores = models.ManyToManyField(Sabor, blank=True)                       # Sabores seleccionados
    addons = models.ManyToManyField(Addon, blank=True)                        # Complementos opcionales
    cantidad = models.PositiveIntegerField(default=1)                         # Cantidad
    precio_unitario = models.DecimalField(max_digits=6, decimal_places=2)     # Precio en el momento de agregar

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} ({self.tamano.nombre})"

# ==============================
# Modelos de perfil de usuario
# ==============================

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Teléfono', max_length=20, blank=True)
    address = models.CharField('Dirección', max_length=255, blank=True)

    def __str__(self):
        return f'Perfil de {self.user.username}'

# Señales para crear/guardar perfil automáticamente
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()