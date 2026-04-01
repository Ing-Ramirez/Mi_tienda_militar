from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import products.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
        ('products', '0007_add_local_category_to_supplier_product'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='productreview',
            name='order',
            field=models.ForeignKey(
                blank=True,
                help_text='Orden que valida la compra del producto.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reviews',
                to='orders.order',
                verbose_name='Orden de compra',
            ),
        ),
        migrations.AddField(
            model_name='productreview',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pendiente de moderación'),
                    ('approved', 'Aprobada'),
                    ('hidden', 'Oculta'),
                ],
                default='pending',
                max_length=20,
                verbose_name='Estado de moderación',
            ),
        ),
        migrations.AlterField(
            model_name='productreview',
            name='title',
            field=models.CharField(blank=True, max_length=100, verbose_name='Título'),
        ),
        migrations.AlterField(
            model_name='productreview',
            name='is_verified_purchase',
            field=models.BooleanField(default=True, verbose_name='Compra verificada'),
        ),
        migrations.CreateModel(
            name='ReviewEvidence',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('image', models.ImageField(
                    upload_to='reviews/',
                    validators=[products.validators.validate_image_file],
                    verbose_name='Imagen',
                )),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Subida el')),
                ('review', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='evidence',
                    to='products.productreview',
                )),
            ],
            options={
                'verbose_name': 'Evidencia de reseña',
                'verbose_name_plural': 'Evidencias de reseñas',
                'ordering': ['uploaded_at'],
            },
        ),
    ]
