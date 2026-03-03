from rest_framework import serializers

from .models import Assignment, StudentAssignment, Submission, Topic
from services.grader_router import DEFAULT_SQL_DB_SETUP, get_schema_summary


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "name", "category", "difficulty_level", "assignment_type"]


class AssignmentListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ["id", "title", "assignment_type", "difficulty", "created_at"]


class AssignmentCreateSerializer(serializers.ModelSerializer):
    topic_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False, default=list
    )

    class Meta:
        model = Assignment
        fields = [
            "title",
            "assignment_type",
            "difficulty",
            "description",
            "requirements",
            "starter_code",
            "public_tests",
            "hidden_tests",
            "grading_rubric",
            "topic_ids",
        ]

    def validate_assignment_type(self, value):
        if value not in dict(Assignment.TYPES):
            raise serializers.ValidationError(f"Must be one of: {list(dict(Assignment.TYPES).keys())}")
        return value

    def validate_difficulty(self, value):
        allowed = ["easy", "medium", "hard"]
        if value not in allowed:
            raise serializers.ValidationError(f"Must be one of: {allowed}")
        return value

    def create(self, validated_data):
        topic_ids = validated_data.pop("topic_ids", [])
        assignment = Assignment.objects.create(**validated_data)
        if topic_ids:
            assignment.topics.set(topic_ids)
        return assignment


class AssignmentDetailSerializer(serializers.ModelSerializer):
    topics = TopicSerializer(many=True, read_only=True)
    table_schema = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            "id",
            "title",
            "assignment_type",
            "difficulty",
            "description",
            "requirements",
            "starter_code",
            "public_tests",
            "hidden_tests",
            "grading_rubric",
            "topics",
            "table_schema",
            "created_at",
        ]

    def get_table_schema(self, obj):
        if obj.assignment_type != "sql":
            return None
        db_setup = (obj.starter_code or {}).get("db_setup", "") or ""
        if not db_setup.strip():
            db_setup = DEFAULT_SQL_DB_SETUP
        return get_schema_summary(db_setup) or None


class StudentAssignmentSerializer(serializers.ModelSerializer):
    assignment = AssignmentListSerializer(read_only=True)
    completed = serializers.SerializerMethodField()

    class Meta:
        model = StudentAssignment
        fields = ["id", "assignment", "assigned_at", "due_date", "completed"]

    def get_completed(self, obj):
        if obj.completed:
            return True
        return Submission.objects.filter(
            assignment=obj.assignment,
            student=obj.student,
        ).exists()


class SubmissionCreateSerializer(serializers.Serializer):
    assignment_id = serializers.IntegerField()
    code = serializers.CharField(required=False, allow_blank=True, default="")
    files = serializers.JSONField(required=False, default=None)

    def validate_assignment_id(self, value):
        if not Assignment.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Assignment not found.")
        return value


class SubmissionDetailSerializer(serializers.ModelSerializer):
    assignment = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id",
            "assignment",
            "status",
            "score",
            "test_results",
            "ai_feedback",
            "submitted_at",
        ]

    def get_assignment(self, obj):
        return {"id": obj.assignment_id, "title": obj.assignment.title}
