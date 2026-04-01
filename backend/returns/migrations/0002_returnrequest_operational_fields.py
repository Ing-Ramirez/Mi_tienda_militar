from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('returns', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='returnrequest',
            name='estimated_refund_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha estimada de reembolso'),
        ),
        migrations.AddField(
            model_name='returnrequest',
            name='return_code',
            field=models.CharField(blank=True, db_index=True, max_length=24, unique=True, verbose_name='Código de devolución'),
        ),
        migrations.AddField(
            model_name='returnrequest',
            name='shipping_deadline_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha límite de envío del cliente'),
        ),
    ]
