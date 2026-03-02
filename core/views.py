import requests
from django.http import JsonResponse
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .constants import POC_MENTOR_ID, POC_STUDENT_ID
from .models import Assignment, StudentAssignment, Submission
from .models import Topic
from .serializers import (
    AssignmentCreateSerializer,
    AssignmentDetailSerializer,
    AssignmentListSerializer,
    StudentAssignmentSerializer,
    SubmissionCreateSerializer,
    SubmissionDetailSerializer,
    TopicSerializer,
)
from services.ai_service import OpenRouterAIService
from services.grader_router import GraderRouter
from services.judge0_service import Judge0Error, Judge0Service


def health(request):
    return JsonResponse({"status": "ok"})


class TopicList(APIView):
    def get(self, request):
        queryset = Topic.objects.all()
        serializer = TopicSerializer(queryset, many=True)
        return Response(serializer.data)


class AssignmentGenerate(APIView):
    def post(self, request):
        topic_ids = request.data.get("topic_ids") or []
        difficulty = request.data.get("difficulty", "").strip().lower()
        assignment_type = (request.data.get("assignment_type") or "").strip().lower()

        if not difficulty or difficulty not in ("easy", "medium", "hard"):
            return Response(
                {"detail": "difficulty is required and must be one of: easy, medium, hard"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not assignment_type or assignment_type not in ("react", "sql", "python", "html_css"):
            return Response(
                {"detail": "assignment_type is required and must be one of: react, sql, python, html_css"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(topic_ids, list):
            return Response(
                {"detail": "topic_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        topics = list(Topic.objects.filter(id__in=[x for x in topic_ids if isinstance(x, int)]))
        service = OpenRouterAIService()
        if not service.api_key:
            return Response(
                {"detail": "OPENROUTER_API_KEY is not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            data = service.generate_assignment(topics, difficulty, assignment_type)
        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except requests.RequestException as e:
            return Response(
                {"detail": f"OpenRouter API error: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(data)


class AssignmentListCreate(APIView):
    def get(self, request):
        queryset = Assignment.objects.filter(mentor_id=POC_MENTOR_ID).order_by("-created_at")
        serializer = AssignmentListSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = AssignmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save(mentor_id=POC_MENTOR_ID)
        return Response(
            AssignmentDetailSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class AssignmentDetail(APIView):
    def get_object(self, pk):
        try:
            return Assignment.objects.get(pk=pk)
        except Assignment.DoesNotExist:
            raise NotFound("Assignment not found.")

    def get(self, request, pk):
        assignment = self.get_object(pk)
        serializer = AssignmentDetailSerializer(assignment)
        return Response(serializer.data)


class AssignmentAssign(APIView):
    def get_object(self, pk):
        try:
            return Assignment.objects.get(pk=pk)
        except Assignment.DoesNotExist:
            raise NotFound("Assignment not found.")

    def post(self, request, pk):
        assignment = self.get_object(pk)
        student_ids = request.data.get("student_ids", [])
        if not isinstance(student_ids, list):
            return Response(
                {"detail": "student_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for sid in student_ids:
            StudentAssignment.objects.get_or_create(
                assignment=assignment,
                student_id=sid,
            )
        return Response({"assigned": len(student_ids)})


class StudentAssignmentList(APIView):
    def get(self, request):
        queryset = (
            StudentAssignment.objects.filter(student_id=POC_STUDENT_ID)
            .select_related("assignment")
            .order_by("-assigned_at")
        )
        serializer = StudentAssignmentSerializer(queryset, many=True)
        return Response(serializer.data)


class SubmissionListCreate(APIView):
    def post(self, request):
        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        submission = Submission.objects.create(
            assignment_id=data["assignment_id"],
            student_id=POC_STUDENT_ID,
            code=data.get("code", ""),
            files=data.get("files"),
            status="grading",
        )
        assignment = submission.assignment
        try:
            result = GraderRouter().grade(submission, assignment)
            submission.score = result["score"]
            submission.test_results = result["test_results"]
            submission.ai_feedback = result["ai_feedback"]
        except (Judge0Error, Exception) as e:
            submission.score = 0.0
            submission.test_results = {
                "error": str(e),
                "passed_tests": 0,
                "total_tests": 1,
                "results": [],
            }
            submission.ai_feedback = None
        submission.status = "completed"
        submission.save()
        return Response(
            SubmissionDetailSerializer(submission).data,
            status=status.HTTP_201_CREATED,
        )


class SubmissionDetail(APIView):
    def get_object(self, pk):
        try:
            return Submission.objects.select_related("assignment").get(pk=pk)
        except Submission.DoesNotExist:
            raise NotFound("Submission not found.")

    def get(self, request, pk):
        submission = self.get_object(pk)
        serializer = SubmissionDetailSerializer(submission)
        return Response(serializer.data)


class RunTests(APIView):
    def post(self, request):
        code = request.data.get("code")
        if code is None:
            return Response(
                {"detail": "code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        assignment_id = request.data.get("assignment_id")
        test_cases = request.data.get("test_cases")
        if assignment_id is not None:
            try:
                assignment = Assignment.objects.get(pk=assignment_id)
            except Assignment.DoesNotExist:
                return Response({"detail": "Assignment not found."}, status=status.HTTP_404_NOT_FOUND)
            test_cases = test_cases or assignment.public_tests or assignment.hidden_tests or []
        if not test_cases:
            return Response(
                {"detail": "Provide assignment_id or test_cases."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            service = Judge0Service()
            result = service.execute_code(code=code, language_id=71, test_cases=test_cases)
            return Response(result)
        except Judge0Error as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
