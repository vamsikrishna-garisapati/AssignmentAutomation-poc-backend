from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLES = [("mentor", "Mentor"), ("student", "Student")]
    role = models.CharField(max_length=10, choices=ROLES)


ASSIGNMENT_TYPES = [
    ("react", "React"),
    ("sql", "SQL"),
    ("python", "Python"),
    ("html_css", "HTML/CSS"),
]


class Topic(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    difficulty_level = models.IntegerField(default=1)
    assignment_type = models.CharField(
        max_length=20, choices=ASSIGNMENT_TYPES, default="python"
    )

    def __str__(self):
        return self.name


class Assignment(models.Model):
    TYPES = ASSIGNMENT_TYPES
    mentor = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    assignment_type = models.CharField(max_length=20, choices=TYPES)
    difficulty = models.CharField(max_length=10)
    description = models.TextField()
    requirements = models.JSONField()
    starter_code = models.JSONField()
    public_tests = models.JSONField()
    hidden_tests = models.JSONField()
    grading_rubric = models.JSONField()
    topics = models.ManyToManyField(Topic, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class StudentAssignment(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = [["assignment", "student"]]

    def __str__(self):
        return f"{self.student} - {self.assignment}"


class Submission(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("grading", "Grading"),
        ("completed", "Completed"),
    ]
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.TextField(blank=True)
    files = models.JSONField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    test_results = models.JSONField(null=True, blank=True)
    ai_feedback = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Submission {self.id} - {self.assignment} by {self.student}"
