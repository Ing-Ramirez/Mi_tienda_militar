# Generated manually — choices mock para pruebas

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0003_proveedor_adapter'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proveedor',
            name='tipo_integracion',
            field=models.CharField(
                choices=[
                    ('api_rest', 'API REST'),
                    ('webhook', 'Solo webhooks'),
                    ('csv', 'Archivo CSV'),
                    ('manual', 'Manual'),
                    ('mock', 'Simulación (sin HTTP — pruebas)'),
                ],
                default='api_rest',
                max_length=20,
                verbose_name='Tipo de integración',
            ),
        ),
        migrations.AlterField(
            model_name='proveedor',
            name='adapter',
            field=models.CharField(
                choices=[
                    ('rest_generico', 'REST JSON genérico (Bearer + /orders/)'),
                    ('dropi', 'Dropi (payload específico — revisar credenciales)'),
                    ('mock', 'Simulación local (respuesta exitosa sin red)'),
                ],
                default='rest_generico',
                help_text='Define el formato de autenticación y payload al enviar pedidos al proveedor.',
                max_length=32,
                verbose_name='Adaptador de API',
            ),
        ),
    ]
