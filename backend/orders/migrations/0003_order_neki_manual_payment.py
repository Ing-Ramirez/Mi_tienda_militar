# Generated manually

import products.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='manual_payment_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('PENDING', 'Pendiente verificación'),
                    ('PAID', 'Comprobante recibido'),
                    ('VERIFIED', 'Pago verificado'),
                    ('REJECTED', 'Pago rechazado'),
                ],
                db_index=True,
                default='',
                help_text='PENDIENTE/VERIFICADO solo para pagos con comprobante (Neki).',
                max_length=20,
                verbose_name='Estado comprobante manual',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='payment_proof',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='payment_proofs/neki/%Y/%m/',
                validators=[products.validators.validate_image_file],
                verbose_name='Comprobante de pago',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='providers_dispatch_enqueued_at',
            field=models.DateTimeField(
                blank=True,
                editable=False,
                help_text='Cuándo se encoló el envío a proveedores (idempotencia).',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                blank=True,
                help_text='Ej: neki, stripe. Solo Neki usa comprobante manual.',
                max_length=50,
            ),
        ),
        migrations.AddIndex(
            model_name='order',
            index=models.Index(fields=['manual_payment_status'], name='ord_manualpay_idx'),
        ),
    ]
