"""
Migration: Rename product fields to English naming convention.

Fields renamed:
  tallas_disponibles → available_sizes
  stock_por_talla    → stock_by_size
  beneficios         → benefits
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_product_beneficios'),
    ]

    operations = [
        migrations.RenameField(
            model_name='product',
            old_name='tallas_disponibles',
            new_name='available_sizes',
        ),
        migrations.RenameField(
            model_name='product',
            old_name='stock_por_talla',
            new_name='stock_by_size',
        ),
        migrations.RenameField(
            model_name='product',
            old_name='beneficios',
            new_name='benefits',
        ),
    ]
