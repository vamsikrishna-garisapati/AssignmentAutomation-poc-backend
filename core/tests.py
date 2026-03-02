from django.test import TestCase
from rest_framework.test import APIClient


class TopicListAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_get_topics_empty(self):
        response = self.client.get("/api/topics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_get_topics_returns_list(self):
        from core.models import Topic

        Topic.objects.create(name="Test", category="Cat", difficulty_level=1)
        response = self.client.get("/api/topics/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Test")
        self.assertEqual(data[0]["category"], "Cat")
        self.assertEqual(data[0]["difficulty_level"], 1)


class AssignmentGenerateAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_generate_requires_difficulty(self):
        response = self.client.post(
            "/api/assignments/generate/",
            {"assignment_type": "python", "topic_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("difficulty", response.json().get("detail", ""))

    def test_generate_requires_valid_assignment_type(self):
        response = self.client.post(
            "/api/assignments/generate/",
            {"difficulty": "easy", "assignment_type": "invalid", "topic_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("assignment_type", response.json().get("detail", ""))

    def test_generate_returns_503_without_api_key(self):
        response = self.client.post(
            "/api/assignments/generate/",
            {"difficulty": "easy", "assignment_type": "python", "topic_ids": []},
            format="json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENROUTER", response.json().get("detail", ""))


class SubmissionGraderTest(TestCase):
    """Phase 4: submission flow uses GraderRouter (no Judge0 required for react)."""

    def setUp(self):
        from core.constants import POC_MENTOR_ID, POC_STUDENT_ID
        from core.models import User, Assignment

        self.client = APIClient()
        User.objects.create(id=POC_MENTOR_ID, username="mentor", role="mentor")
        User.objects.create(id=POC_STUDENT_ID, username="student", role="student")
        self.assignment = Assignment.objects.create(
            mentor_id=POC_MENTOR_ID,
            title="React Test",
            assignment_type="react",
            difficulty="easy",
            description="Test",
            requirements=["use useState", "return div"],
            starter_code={},
            public_tests=[],
            hidden_tests=[],
            grading_rubric={"correctness": 60, "code_quality": 20, "edge_cases": 20},
        )

    def test_submission_returns_grader_results(self):
        response = self.client.post(
            "/api/submissions/",
            {
                "assignment_id": self.assignment.id,
                "code": "",
                "files": {"/App.js": "import { useState } from 'react'; const App = () => { return <div>Hi</div>; }; export default App;"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertIn("score", data)
        self.assertIsInstance(data.get("score"), (int, float))
        self.assertIn("test_results", data)
        self.assertIn("passed_tests", data["test_results"])
        self.assertIn("total_tests", data["test_results"])
