from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_rename_ord_manualpay_idx_orders_orde_manual__557d42_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='loyalty_points_used',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='Puntos usados',
                help_text='Puntos de fidelidad aplicados como descuento en esta orden.',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_discount_amount',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                verbose_name='Descuento por puntos (COP)',
                help_text='Valor en COP descontado gracias a puntos de fidelidad.',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_points_earned',
            field=models.PositiveIntegerField(
                default=0,
                editable=False,
                verbose_name='Puntos ganados',
                help_text='Puntos acreditados al usuario tras confirmar el pago.',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='loyalty_points_processed',
            field=models.BooleanField(
                default=False,
                editable=False,
                db_index=True,
                verbose_name='Puntos procesados',
                help_text='Bandera de idempotencia: True cuando los puntos ya fueron acreditados.',
            ),
        ),
    ]
