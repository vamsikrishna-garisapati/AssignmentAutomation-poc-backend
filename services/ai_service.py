"""
OpenRouter AI service for assignment generation and feedback.
"""
import json
import os
import re

import requests


class OpenRouterAIService:
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    MODELS = {
        "generation": "deepseek/deepseek-r1-distill-qwen-32b",
        "feedback": "google/gemini-2.0-flash-thinking-exp:free",
    }

    REQUIRED_ASSIGNMENT_KEYS = [
        "title",
        "assignment_type",
        "difficulty",
        "description",
        "requirements",
        "starter_code",
        "public_tests",
        "hidden_tests",
        "grading_rubric",
    ]

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

    def _call_api(self, prompt, model):
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
        }
        response = requests.post(
            self.BASE_URL,
            json=payload,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        choice = data.get("choices")
        if not choice:
            raise ValueError("OpenRouter response has no choices")
        content = choice[0].get("message", {}).get("content", "")
        if not content:
            raise ValueError("OpenRouter response has empty content")
        return content.strip()

    def _strip_markdown_json(self, raw):
        text = raw.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _parse_and_validate_assignment(self, raw):
        text = self._strip_markdown_json(raw)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON from AI: {e}") from e

        if not isinstance(data, dict):
            raise ValueError("AI response is not a JSON object")

        missing = [k for k in self.REQUIRED_ASSIGNMENT_KEYS if k not in data]
        if missing:
            raise ValueError(f"Missing required keys: {missing}")

        for key in ["requirements", "public_tests", "hidden_tests"]:
            if not isinstance(data.get(key), list):
                raise ValueError(f"'{key}' must be a list")
        if not isinstance(data.get("starter_code"), dict):
            raise ValueError("'starter_code' must be an object")
        if not isinstance(data.get("grading_rubric"), dict):
            raise ValueError("'grading_rubric' must be an object")

        return data

    def _build_generation_prompt(self, topics, difficulty, assignment_type):
        type_instructions = {
            "react": "Sandpack-compatible React component, functional components only. Use starter_code key 'react' with JSX code for /App.js.",
            "sql": "SQLite-compatible SQL. Include a 'db_setup' key with CREATE TABLE and INSERT statements. Use starter_code for the initial query template.",
            "python": "Standard Python 3. Use stdin/stdout for test cases (input/expected_output strings). Test format: name, input, expected_output.",
            "html_css": "Vanilla HTML + CSS, no frameworks. starter_code can have 'html' and 'css' keys.",
        }
        topic_names = [t.name for t in topics] if topics else ["General programming"]
        instructions = type_instructions.get(
            assignment_type,
            "Return valid JSON matching the schema.",
        )
        return f"""Generate a coding assignment. Return ONLY valid JSON (no markdown, no explanation) matching this exact schema:

{{
  "title": "string",
  "assignment_type": "{assignment_type}",
  "difficulty": "{difficulty}",
  "description": "string (clear task description for the student)",
  "requirements": ["requirement 1", "requirement 2"],
  "starter_code": {{ "{(assignment_type if assignment_type != 'html_css' else 'html')}": "code or comment placeholder" }},
  "db_setup": "CREATE TABLE ... ; INSERT ... (only for sql type; omit or empty string for others)",
  "public_tests": [
    {{ "name": "Test name", "input": "...", "expected_output": "..." }}
  ],
  "hidden_tests": [
    {{ "name": "Hidden test", "input": "...", "expected_output": "..." }}
  ],
  "grading_rubric": {{ "correctness": 60, "code_quality": 20, "edge_cases": 20 }}
}}

Topics: {topic_names}
Difficulty: {difficulty}
Assignment type: {assignment_type}
Special instructions: {instructions}
"""

    def generate_assignment(self, topics, difficulty, assignment_type):
        prompt = self._build_generation_prompt(topics, difficulty, assignment_type)
        raw = self._call_api(prompt, model=self.MODELS["generation"])
        return self._parse_and_validate_assignment(raw)

    def generate_feedback(self, code, test_results, requirements):
        prompt = f"""Provide constructive feedback for this code submission.
Return ONLY valid JSON (no markdown) with this exact structure:
{{
  "summary": "brief overview in 1-2 sentences",
  "strengths": ["strength 1", "strength 2"],
  "improvements": ["improvement 1", "improvement 2"],
  "hints": ["one next-step hint"]
}}

Test Results: {json.dumps(test_results, default=str)}
Requirements: {json.dumps(requirements, default=str)}
Code:
{code}
"""
        raw = self._call_api(prompt, model=self.MODELS["feedback"])
        text = self._strip_markdown_json(raw)
        data = json.loads(text)
        for key in ["summary", "strengths", "improvements", "hints"]:
            if key not in data:
                data[key] = [] if key in ("strengths", "improvements", "hints") else ""
        return data
