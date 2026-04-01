# Generated manually — permite varias solicitudes por orden (p. ej. tras rechazo).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('returns', '0002_returnrequest_operational_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='returnrequest',
            name='order',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='return_requests',
                to='orders.order',
                verbose_name='Orden',
            ),
        ),
    ]
