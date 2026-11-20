from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_course_payments"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymenttransaction",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
