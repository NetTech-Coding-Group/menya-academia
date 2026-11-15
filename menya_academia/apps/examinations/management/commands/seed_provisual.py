from django.conf import settings
from django.core.management.base import BaseCommand

from apps.provisual.models import Exam, ExamPackage


class Command(BaseCommand):
    help = "Create the default PROVISUAL packages and practice exam settings."

    def handle(self, *args, **options):
        packages = (
            ("Single Examination", ExamPackage.PackageType.SINGLE, 200, 1, 1),
            ("Weekly Package", ExamPackage.PackageType.WEEKLY, 4000, 7, 0),
            ("Two Weeks Package", ExamPackage.PackageType.TWO_WEEKS, 7000, 14, 0),
            ("Monthly Package", ExamPackage.PackageType.MONTHLY, 100000, 30, 0),
        )
        for order, (name, package_type, price, days, attempts) in enumerate(
            packages, start=1
        ):
            ExamPackage.objects.get_or_create(
                package_type=package_type,
                defaults={
                    "name": name,
                    "price_rwf": price,
                    "duration_days": days,
                    "max_exam_attempts": attempts,
                    "is_active": True,
                    "display_order": order,
                },
            )
        Exam.objects.get_or_create(
            slug="practice",
            defaults={
                "title": "PROVISUAL Practice Exam",
                "question_count": settings.EXAM_QUESTION_COUNT,
                "duration_minutes": settings.EXAM_DURATION_MINUTES,
                "pass_mark": settings.EXAM_PASS_MARK,
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Default PROVISUAL data is ready."))
