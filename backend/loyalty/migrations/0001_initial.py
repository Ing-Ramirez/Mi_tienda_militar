import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0005_order_loyalty_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LoyaltyAccount',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('points_balance', models.IntegerField(default=0, help_text='Puntos disponibles para redimir.', verbose_name='Saldo actual (pts)')),
                ('total_earned', models.IntegerField(default=0, verbose_name='Total acumulado histórico (pts)')),
                ('total_redeemed', models.IntegerField(default=0, verbose_name='Total redimido histórico (pts)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creada el')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizada el')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='loyalty_account',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuario',
                )),
            ],
            options={
                'verbose_name': 'Cuenta de Fidelidad',
                'verbose_name_plural': 'Cuentas de Fidelidad',
            },
        ),
        migrations.CreateModel(
            name='PointTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('transaction_type', models.CharField(
                    choices=[
                        ('earn', 'Acumulación'),
                        ('redeem', 'Redención'),
                        ('reverse_earn', 'Reverso de acumulación'),
                        ('reverse_redeem', 'Reverso de redención'),
                        ('adjustment', 'Ajuste manual'),
                    ],
                    db_index=True,
                    max_length=20,
                    verbose_name='Tipo',
                )),
                ('points', models.IntegerField(help_text='Positivo = crédito, negativo = débito.', verbose_name='Puntos')),
                ('balance_after', models.IntegerField(help_text='Saldo de la cuenta inmediatamente después de esta transacción.', verbose_name='Saldo resultante')),
                ('description', models.TextField(blank=True, verbose_name='Descripción')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='Metadata')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Fecha')),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transactions',
                    to='loyalty.loyaltyaccount',
                    verbose_name='Cuenta',
                )),
                ('order', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='loyalty_transactions',
                    to='orders.order',
                    verbose_name='Orden',
                )),
            ],
            options={
                'verbose_name': 'Transacción de Puntos',
                'verbose_name_plural': 'Transacciones de Puntos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='loyaltyaccount',
            index=models.Index(fields=['user'], name='loyalty_acc_user_idx'),
        ),
        migrations.AddIndex(
            model_name='pointtransaction',
            index=models.Index(fields=['account', '-created_at'], name='loyalty_tx_account_date_idx'),
        ),
        migrations.AddIndex(
            model_name='pointtransaction',
            index=models.Index(fields=['order'], name='loyalty_tx_order_idx'),
        ),
    ]
