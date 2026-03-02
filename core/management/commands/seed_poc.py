"""
Seed POC data: one mentor (id=1), one student (id=2), and sample topics.
Run: python manage.py seed_poc
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.constants import POC_MENTOR_ID, POC_STUDENT_ID
from core.models import User, Topic


class Command(BaseCommand):
    help = "Seed one mentor, one student, and sample topics for POC."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recreate users/topics if they already exist (resets passwords).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force"]

        # Mentor (id=1) — explicit id so API can use default mentor_id=1
        mentor, created = User.objects.update_or_create(
            id=POC_MENTOR_ID,
            defaults={
                "username": "mentor",
                "email": "mentor@poc.local",
                "role": "mentor",
                "is_staff": True,
            },
        )
        mentor.set_password("mentor")
        mentor.save()
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} mentor (id={POC_MENTOR_ID})")
        )

        # Student (id=2) — explicit id so API can use default student_id=2
        student, created = User.objects.update_or_create(
            id=POC_STUDENT_ID,
            defaults={
                "username": "student",
                "email": "student@poc.local",
                "role": "student",
            },
        )
        student.set_password("student")
        student.save()
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Updated'} student (id={POC_STUDENT_ID})")
        )

        # Topics
        topics_data = [
            {"name": "React Hooks", "category": "Frontend", "difficulty_level": 2},
            {"name": "SQL Joins", "category": "Database", "difficulty_level": 2},
            {"name": "Python Basics", "category": "Backend", "difficulty_level": 1},
            {"name": "HTML/CSS Layout", "category": "Frontend", "difficulty_level": 1},
        ]
        for t in topics_data:
            topic, created = Topic.objects.get_or_create(
                name=t["name"],
                defaults={"category": t["category"], "difficulty_level": t["difficulty_level"]},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created topic: {topic.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"POC seed done. Default mentor_id={POC_MENTOR_ID}, student_id={POC_STUDENT_ID}."
            )
        )
