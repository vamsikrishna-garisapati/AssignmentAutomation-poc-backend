from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Topic, Assignment, StudentAssignment, Submission


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "role", "is_staff"]
    list_filter = ["role"]
    fieldsets = BaseUserAdmin.fieldsets + (("POC", {"fields": ("role",)}),)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "difficulty_level"]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ["title", "assignment_type", "difficulty", "mentor", "created_at"]
    list_filter = ["assignment_type", "difficulty"]
    filter_horizontal = ["topics"]


@admin.register(StudentAssignment)
class StudentAssignmentAdmin(admin.ModelAdmin):
    list_display = ["assignment", "student", "assigned_at", "completed"]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["id", "assignment", "student", "status", "score", "submitted_at"]
    list_filter = ["status"]
