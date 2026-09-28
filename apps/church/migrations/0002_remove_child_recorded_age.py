from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("church", "0001_initial")]

    operations = [migrations.RemoveField(model_name="child", name="recorded_age")]
