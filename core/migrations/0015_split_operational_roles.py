from django.db import migrations


def create_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    masters, _ = Group.objects.get_or_create(name='masters')
    Group.objects.get_or_create(name='dispatchers')
    for user in User.objects.filter(is_staff=True, is_superuser=False):
        user.groups.add(masters)


def remove_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=('masters', 'dispatchers')).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0014_clientnotification'),
    ]

    operations = [
        migrations.RunPython(create_roles, remove_roles),
    ]
