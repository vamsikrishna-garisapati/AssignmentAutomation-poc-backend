"""
Gemini AI service for assignment generation and feedback.
Uses GROQ as fallback when Gemini returns 429 (rate limit).
"""
import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)


class GeminiAIService:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    # Latest stable: gemini-2.5-pro (deep reasoning). Override with env GEMINI_MODEL if needed.
    MODEL = "gemini-2.5-pro"
    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    GROQ_MODEL = "llama-3.3-70b-versatile"

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
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.model = (os.environ.get("GEMINI_MODEL", "").strip() or self.MODEL)
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.groq_model = (os.environ.get("GROQ_MODEL", "").strip() or self.GROQ_MODEL)

    def _call_gemini(self, prompt, model=None):
        model = model or self.model
        url = f"{self.BASE_URL}/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ],
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        if response.status_code == 429:
            raise requests.HTTPError("429 Rate limit", response=response)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates")
        if not candidates:
            raise ValueError("Gemini response has no candidates")
        parts = candidates[0].get("content", {}).get("parts")
        if not parts:
            raise ValueError("Gemini response has no content parts")
        text = parts[0].get("text", "")
        if not text:
            raise ValueError("Gemini response has empty text")
        return text.strip()

    def _call_groq(self, prompt):
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set (required for 429 fallback)")
        payload = {
            "model": self.groq_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            self.GROQ_URL, json=payload, headers=headers, timeout=120
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices")
        if not choices:
            raise ValueError("GROQ response has no choices")
        text = choices[0].get("message", {}).get("content", "")
        if not text:
            raise ValueError("GROQ response has empty content")
        return text.strip()

    def _call_api(self, prompt, model=None):
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set")

        try:
            return self._call_gemini(prompt, model=model)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429 and self.groq_api_key:
                logger.warning("Gemini 429 rate limit; falling back to GROQ")
                return self._call_groq(prompt)
            raise

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

    def _build_generation_prompt(
        self, topics, difficulty, assignment_type, sub_topic=None, additional_information=None
    ):
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
        prompt = f"""Generate a coding assignment. Return ONLY valid JSON (no markdown, no explanation) matching this exact schema:

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
        extra = []
        if sub_topic:
            extra.append(f"Sub topic / focus: {sub_topic}")
        if additional_information:
            extra.append(f"Additional instructions from mentor: {additional_information}")
        if extra:
            return prompt.rstrip() + "\n" + "\n".join(extra) + "\n"
        return prompt

    def generate_assignment(
        self, topics, difficulty, assignment_type, sub_topic=None, additional_information=None
    ):
        prompt = self._build_generation_prompt(
            topics, difficulty, assignment_type,
            sub_topic=sub_topic,
            additional_information=additional_information,
        )
        raw = self._call_api(prompt)
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
        raw = self._call_api(prompt)
        text = self._strip_markdown_json(raw)
        data = json.loads(text)
        for key in ["summary", "strengths", "improvements", "hints"]:
            if key not in data:
                data[key] = [] if key in ("strengths", "improvements", "hints") else ""
        return data
