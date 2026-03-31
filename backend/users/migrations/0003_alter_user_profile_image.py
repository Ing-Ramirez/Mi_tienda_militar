from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_profile_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='profile_image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='protected/profile_images/',
                verbose_name='Foto de perfil',
            ),
        ),
    ]
