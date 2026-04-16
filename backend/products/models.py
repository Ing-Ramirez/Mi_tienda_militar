"""
Franja Pixelada — Modelos de Productos
Incluye: Category, Tag, Product, ProductImage, ProductVariant,
         ProductReview, InventoryLog, Favorito
"""
from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from products.validators import validate_image_file
import uuid

_COLOR_HEX_VALIDATOR = RegexValidator(
    regex=r'^$|^#[0-9A-Fa-f]{6}$',
    message='Use un color hexadecimal # seguido de 6 caracteres (0-9, A-F) o deje en blanco.',
)


class Category(models.Model):
    """Categorías de productos tácticos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, verbose_name='Nombre')
    slug = models.SlugField(unique=True, blank=True, verbose_name='Identificador URL',
                            help_text='Se genera automáticamente del nombre')
    description = models.TextField(blank=True, verbose_name='Descripción')
    icon = models.CharField(max_length=50, blank=True, verbose_name='Icono',
                            help_text='Clase Font Awesome, ej: fas fa-tshirt')
    image = models.ImageField(upload_to='categories/', blank=True, null=True,
                              verbose_name='Imagen', validators=[validate_image_file])
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='subcategories',
        verbose_name='Categoría padre'
    )
    is_active = models.BooleanField(default=True, verbose_name='Activa')
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creada el')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizada el')

    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    """Etiquetas para productos"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Nombre')
    slug = models.SlugField(unique=True, blank=True, verbose_name='Identificador URL')

    class Meta:
        verbose_name = 'Etiqueta'
        verbose_name_plural = 'Etiquetas'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    """Modelo principal de productos"""
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('inactive', 'Inactivo'),
        ('out_of_stock', 'Agotado'),
        ('coming_soon', 'Próximamente'),
    ]

    PERSONALIZATION_CHOICES = [
        ('none', 'Sin personalización'),
        ('bordado', 'Texto bordado (apellido)'),
        ('rh', 'Grupo sanguíneo (RH)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku = models.CharField(max_length=50, unique=True, verbose_name='SKU')
    name = models.CharField(max_length=200, verbose_name='Nombre')
    slug = models.SlugField(unique=True, blank=True, max_length=250,
                            verbose_name='Slug (URL)',
                            help_text='Se genera automáticamente del nombre')
    description = models.TextField(verbose_name='Descripción')
    short_description = models.CharField(max_length=300, blank=True,
                                         verbose_name='Descripción corta')

    # Precios
    price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Precio (COP)'
    )
    compare_at_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Precio anterior (COP)'
    )
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(0)],
        verbose_name='Precio de costo (COP)'
    )

    # Organización
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT,
        related_name='products', verbose_name='Categoría'
    )
    tags = models.ManyToManyField(Tag, blank=True, verbose_name='Etiquetas')

    # Tallas
    available_sizes = models.JSONField(
        default=list, blank=True,
        verbose_name='Tallas disponibles',
        help_text="Calculado automáticamente desde stock_by_size"
    )
    requires_size = models.BooleanField(default=False, verbose_name='Requiere talla')
    stock_by_size = models.JSONField(
        default=dict, blank=True,
        verbose_name='Stock por talla',
        help_text='Gestionado desde la interfaz de tallas. Ej: {"S": 5, "M": 10}'
    )

    # Contenido comercial
    benefits = models.JSONField(
        default=list, blank=True,
        verbose_name='Beneficios',
        help_text='Lista de hasta 5 beneficios cortos. Ej: ["Alta resistencia", "Tela ignífuga"]'
    )

    # Personalización
    personalization_type = models.CharField(
        max_length=20, choices=PERSONALIZATION_CHOICES,
        default='none', verbose_name='Tipo de personalización'
    )

    # Inventario
    stock = models.PositiveIntegerField(default=0, verbose_name='Stock')
    low_stock_threshold = models.PositiveIntegerField(default=5,
                                                      verbose_name='Stock mínimo de alerta')
    track_inventory = models.BooleanField(default=True, verbose_name='Controlar inventario')

    # Atributos físicos
    weight = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        verbose_name='Peso (kg)',
        help_text='Peso en kilogramos'
    )

    # Estado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active',
                               verbose_name='Estado')
    is_featured = models.BooleanField(default=False, verbose_name='Destacado')
    is_new = models.BooleanField(default=False, verbose_name='Nuevo')

    # SEO
    meta_title = models.CharField(max_length=200, blank=True, verbose_name='Título SEO')
    meta_description = models.CharField(max_length=300, blank=True,
                                        verbose_name='Descripción SEO')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'category']),
            models.Index(fields=['slug']),
            models.Index(fields=['sku']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f'{self.sku} - {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            counter = 1
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f'{slugify(self.name)}-{counter}'
                counter += 1
        # requires_size es el campo controlador — nunca se auto-asigna aquí.
        if self.requires_size:
            # Producto CON talla: stock y tallas se calculan desde stock_by_size
            sbs = self.stock_by_size if isinstance(self.stock_by_size, dict) else {}
            tallas_activas = [t for t, s in sbs.items() if s and int(s) > 0]
            self.available_sizes = tallas_activas
            self.stock = sum(int(s) for s in sbs.values() if s and int(s) > 0)
        else:
            # Producto SIN talla: stock global manual, limpiar datos de tallas
            self.available_sizes = []
            self.stock_by_size = {}
        super().save(*args, **kwargs)

    @property
    def is_in_stock(self):
        if not self.track_inventory:
            return True
        return self.stock > 0

    @property
    def is_low_stock(self):
        return self.track_inventory and 0 < self.stock <= self.low_stock_threshold

    @property
    def discount_percentage(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            discount = ((self.compare_at_price - self.price) / self.compare_at_price) * 100
            return round(discount)
        return None

    @property
    def main_image(self):
        img = self.images.filter(is_primary=True).first()
        return img or self.images.first()


class ProductImage(models.Model):
    """Imágenes de productos"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images',
                                verbose_name='Producto')
    image = models.ImageField(upload_to='products/', validators=[validate_image_file],
                              verbose_name='Imagen')
    alt_text = models.CharField(max_length=200, blank=True, verbose_name='Texto alternativo')
    is_primary = models.BooleanField(default=False, verbose_name='Principal')
    order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de subida')

    class Meta:
        verbose_name = 'Imagen de Producto'
        verbose_name_plural = 'Imágenes de Producto'
        ordering = ['order', 'created_at']

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    """Variantes de productos (tallas, colores, modelos, fondos)"""
    VARIANT_TYPE_CHOICES = [
        ('talla', 'Talla'),
        ('color', 'Color'),
        ('fondo', 'Fondo'),
        ('modelo', 'Modelo'),
        ('otro', 'Otro'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants',
                                verbose_name='Producto')
    variant_type = models.CharField(
        max_length=20, choices=VARIANT_TYPE_CHOICES,
        default='talla', verbose_name='Tipo de variante'
    )
    name = models.CharField(max_length=100, verbose_name='Nombre',
                            help_text='Ej: Talla M — Fondo Verde')
    sku = models.CharField(max_length=50, unique=True, verbose_name='Código SKU')
    price_adjustment = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Ajuste de precio',
        help_text='Ajuste al precio base (+/- COP)'
    )
    stock = models.PositiveIntegerField(default=0, verbose_name='Stock')
    size = models.CharField(max_length=20, blank=True, verbose_name='Talla / Tamaño')
    color = models.CharField(max_length=50, blank=True, verbose_name='Color')
    color_hex = models.CharField(
        max_length=7, blank=True, verbose_name='Código de color (hex)',
        validators=[_COLOR_HEX_VALIDATOR],
    )
    image = models.ImageField(upload_to='variants/', blank=True, null=True,
                              verbose_name='Imagen', validators=[validate_image_file])
    is_active = models.BooleanField(default=True, verbose_name='Activa')

    class Meta:
        verbose_name = 'Variante'
        verbose_name_plural = 'Variantes'

    def __str__(self):
        return f'{self.product.name} - {self.name}'

    @property
    def final_price(self):
        return self.product.price + self.price_adjustment


class ProductReview(models.Model):
    """Reseñas de productos — solo para compradores verificados"""
    STATUS_CHOICES = [
        ('pending',  'Pendiente de moderación'),
        ('approved', 'Aprobada'),
        ('hidden',   'Oculta'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='reviews')
    order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviews',
        verbose_name='Orden de compra',
        help_text='Orden que valida la compra del producto.'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='Calificación'
    )
    title = models.CharField(max_length=100, blank=True, verbose_name='Título')
    comment = models.TextField(verbose_name='Comentario')
    is_verified_purchase = models.BooleanField(default=True, verbose_name='Compra verificada')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
        verbose_name='Estado de moderación'
    )
    # Campo de compatibilidad retroactiva — sincronizado con status=='approved'
    is_approved = models.BooleanField(default=False, verbose_name='Aprobada')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizada')

    class Meta:
        verbose_name = 'Reseña'
        verbose_name_plural = 'Reseñas'
        unique_together = ['product', 'user', 'order']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} - {self.rating}★ por {self.user.email}'

    def save(self, *args, **kwargs):
        self.is_approved = (self.status == 'approved')
        super().save(*args, **kwargs)


class ReviewEvidence(models.Model):
    """Imágenes de evidencia adjuntadas a una reseña por el cliente"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.ForeignKey(
        ProductReview, on_delete=models.CASCADE, related_name='evidence'
    )
    image = models.ImageField(
        upload_to='reviews/', validators=[validate_image_file],
        verbose_name='Imagen'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Subida el')

    class Meta:
        verbose_name = 'Evidencia de reseña'
        verbose_name_plural = 'Evidencias de reseñas'
        ordering = ['uploaded_at']

    def __str__(self):
        return f'Evidencia de {self.review}'


class InventoryLog(models.Model):
    """Registro de movimientos de inventario"""
    ACTION_CHOICES = [
        ('add', 'Adición'),
        ('remove', 'Retiro'),
        ('sale', 'Venta'),
        ('return', 'Devolución'),
        ('adjustment', 'Ajuste'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='inventory_logs', verbose_name='Producto')
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Variante'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='Acción')
    quantity_change = models.IntegerField(
        verbose_name='Cambio de cantidad',
        help_text='Positivo para entradas, negativo para salidas'
    )
    stock_before = models.IntegerField(verbose_name='Stock anterior')
    stock_after = models.IntegerField(verbose_name='Stock resultante')
    notes = models.TextField(blank=True, verbose_name='Notas')
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Registrado por'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha')

    class Meta:
        verbose_name = 'Movimiento de Inventario'
        verbose_name_plural = 'Movimientos de Inventario'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} [{self.action}] ({self.quantity_change:+d})'


class Favorito(models.Model):
    """Productos marcados como favoritos por el usuario"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='favoritos'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='favoritos'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Favorito'
        verbose_name_plural = 'Favoritos'
        unique_together = ['user', 'product']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} — {self.product.name}'
