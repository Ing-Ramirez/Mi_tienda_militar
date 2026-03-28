from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='stock_por_talla',
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name='Stock por talla',
                help_text='Gestionado desde la interfaz de tallas. Ej: {"S": 5, "M": 10}',
            ),
        ),
    ]
