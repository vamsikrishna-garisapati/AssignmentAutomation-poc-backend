"""
Judge0 service for executing Python (and other) code with test cases.
"""
import os
import time

import requests


class Judge0Error(Exception):
    """Raised when Judge0 API is unavailable or returns an error."""
    pass


# Judge0 status: 1 In Queue, 2 Processing, 3 Accepted, 4-20 various errors
STATUS_IN_QUEUE = 1
STATUS_PROCESSING = 2
STATUS_ACCEPTED = 3
STATUS_FINISHED_IDS = (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)

# Python 3
LANGUAGE_ID_PYTHON = 71


class Judge0Service:
    def __init__(self):
        self.base_url = (os.environ.get("JUDGE0_API_URL") or "").rstrip("/")
        self.api_key = (os.environ.get("JUDGE0_API_KEY") or "").strip()

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Auth-Token"] = self.api_key
        return headers

    def _check_configured(self):
        if not self.base_url:
            raise Judge0Error("JUDGE0_API_URL is not set")

    def execute_code(self, code, language_id=LANGUAGE_ID_PYTHON, test_cases=None):
        """
        Run code with each test case (stdin -> compare stdout to expected_output).
        test_cases: list of {"input": str, "expected_output": str, "name": str (optional)}
        Returns: {"passed_tests": int, "total_tests": int, "results": [{"name", "passed", "expected", "actual", "error"?}]}
        """
        self._check_configured()
        test_cases = test_cases or []
        if not test_cases:
            return {"passed_tests": 0, "total_tests": 0, "results": []}

        results = []
        for i, tc in enumerate(test_cases):
            name = tc.get("name") or f"Test {i + 1}"
            expected = (tc.get("expected_output") or "").strip()
            stdin = tc.get("input") or ""

            try:
                token = self._create_submission(code, language_id, stdin)
                stdout, stderr, status_id, message = self._wait_and_get_output(token)
                actual = (stdout or "").strip()
                passed = status_id == STATUS_ACCEPTED and actual == expected
                if passed:
                    results.append({"name": name, "passed": True, "expected": expected, "actual": actual})
                else:
                    error = None
                    if status_id != STATUS_ACCEPTED:
                        error = message or stderr or f"Status id {status_id}"
                    results.append({
                        "name": name,
                        "passed": False,
                        "expected": expected,
                        "actual": actual,
                        "error": error,
                    })
            except Judge0Error as e:
                results.append({
                    "name": name,
                    "passed": False,
                    "expected": expected,
                    "actual": "",
                    "error": str(e),
                })

        passed_tests = sum(1 for r in results if r.get("passed"))
        return {
            "passed_tests": passed_tests,
            "total_tests": len(results),
            "results": results,
        }

    def _create_submission(self, source_code, language_id, stdin):
        url = f"{self.base_url}/submissions"
        params = {"base64_encoded": "false", "wait": "false"}
        payload = {
            "source_code": source_code,
            "language_id": language_id,
            "stdin": stdin,
        }
        try:
            r = requests.post(url, params=params, json=payload, headers=self._headers(), timeout=15)
            r.raise_for_status()
            data = r.json()
            token = data.get("token")
            if not token:
                raise Judge0Error("Judge0 did not return a token")
            return token
        except requests.RequestException as e:
            raise Judge0Error(f"Judge0 create submission failed: {e}") from e

    def _get_submission(self, token):
        url = f"{self.base_url}/submissions/{token}"
        params = {"base64_encoded": "false"}
        try:
            r = requests.get(url, params=params, headers=self._headers(), timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise Judge0Error(f"Judge0 get submission failed: {e}") from e

    def _wait_and_get_output(self, token, timeout=30, poll_interval=0.5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self._get_submission(token)
            status = data.get("status") or {}
            status_id = status.get("id")
            if status_id in STATUS_FINISHED_IDS:
                stdout = data.get("stdout") or ""
                stderr = data.get("stderr") or ""
                message = data.get("message") or status.get("description") or ""
                return stdout, stderr, status_id, message
            time.sleep(poll_interval)
        raise Judge0Error("Judge0 submission timed out")
