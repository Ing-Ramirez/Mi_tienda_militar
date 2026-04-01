# Rechazo subsanable/definitivo, reintento con parent_return, límites de intento.

import django.db.models.deletion
from django.db import migrations, models


def forwards_rejected_to_subsanable(apps, schema_editor):
    ReturnRequest = apps.get_model('returns', 'ReturnRequest')
    ReturnRequest.objects.filter(status='rejected').update(status='rejected_subsanable')


def noop_reverse(apps, schema_editor):
    ReturnRequest = apps.get_model('returns', 'ReturnRequest')
    ReturnRequest.objects.filter(status='rejected_subsanable').update(status='rejected')


class Migration(migrations.Migration):

    dependencies = [
        ('returns', '0003_alter_returnrequest_order_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='returnrequest',
            name='attempt_number',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='Número de intento'),
        ),
        migrations.AddField(
            model_name='returnrequest',
            name='parent_return',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='child_returns',
                to='returns.returnrequest',
                verbose_name='Solicitud anterior',
            ),
        ),
        migrations.AddField(
            model_name='returnrequest',
            name='rejected_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de rechazo'),
        ),
        migrations.AddField(
            model_name='returnrequest',
            name='rejection_reason',
            field=models.TextField(blank=True, verbose_name='Motivo de rechazo (visible al cliente)'),
        ),
        migrations.RunPython(forwards_rejected_to_subsanable, noop_reverse),
        migrations.AlterField(
            model_name='returnrequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('requested', 'Solicitada'),
                    ('reviewing', 'En revisión'),
                    ('approved', 'Aprobada'),
                    ('rejected_subsanable', 'Rechazada (subsanable)'),
                    ('rejected_definitive', 'Rechazada (definitiva)'),
                    ('in_transit', 'En envío (cliente devuelve)'),
                    ('received', 'Recibida'),
                    ('validated', 'Validada'),
                    ('refunded', 'Reembolsada'),
                    ('closed', 'Cerrada'),
                ],
                db_index=True,
                default='requested',
                max_length=22,
                verbose_name='Estado',
            ),
        ),
        migrations.AlterField(
            model_name='returnauditlog',
            name='from_status',
            field=models.CharField(max_length=22, verbose_name='Estado anterior'),
        ),
        migrations.AlterField(
            model_name='returnauditlog',
            name='to_status',
            field=models.CharField(max_length=22, verbose_name='Estado nuevo'),
        ),
    ]
