import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0001_initial"),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymenttransaction",
            name="course",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments",
                to="courses.course",
            ),
        ),
        migrations.AlterField(
            model_name="paymenttransaction",
            name="package",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="provisual.exampackage",
            ),
        ),
        migrations.AddConstraint(
            model_name="paymenttransaction",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(package__isnull=False, course__isnull=True)
                    | models.Q(package__isnull=True, course__isnull=False)
                ),
                name="payment_has_exactly_one_product",
            ),
        ),
    ]
