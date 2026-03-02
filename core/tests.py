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
