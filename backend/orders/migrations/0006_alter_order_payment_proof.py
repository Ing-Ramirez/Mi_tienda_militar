import products.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_order_loyalty_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='payment_proof',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='protected/payment_proofs/neki/%Y/%m/',
                validators=[products.validators.validate_image_file],
                verbose_name='Comprobante de pago',
            ),
        ),
    ]
