"""
GraderRouter: routes to the correct grader by assignment type, computes score, and fetches AI feedback.
"""
import sqlite3

from bs4 import BeautifulSoup

from services.ai_service import OpenRouterAIService
from services.judge0_service import Judge0Service, Judge0Error, LANGUAGE_ID_PYTHON


def _rows_to_comparable(rows, keys):
    """Convert list of sqlite3.Row or tuples to list of dicts or tuples for comparison."""
    if not rows:
        return []
    if hasattr(rows[0], "keys"):
        return [dict(r) for r in rows]
    if keys:
        return [dict(zip(keys, r)) for r in rows]
    return [tuple(r) for r in rows]


class GraderRouter:
    def grade(self, submission, assignment):
        """
        Returns {"score": float, "test_results": dict, "ai_feedback": dict | None}.
        """
        atype = assignment.assignment_type

        # Step 1: Deterministic grading
        if atype == "python":
            test_results = self._grade_python(submission, assignment)
        elif atype == "sql":
            test_results = self._grade_sql(submission, assignment)
        elif atype == "react":
            test_results = self._grade_react(submission, assignment)
        elif atype == "html_css":
            test_results = self._grade_html_css(submission, assignment)
        else:
            test_results = {"passed_tests": 0, "total_tests": 1, "results": [], "error": f"Unknown type: {atype}"}

        # Step 2: Score
        score = self._calculate_score(test_results, assignment.grading_rubric or {})

        # Step 3: AI feedback
        code_for_feedback = self._code_for_feedback(submission, atype)
        ai_feedback = None
        try:
            ai_service = OpenRouterAIService()
            if ai_service.api_key:
                ai_feedback = ai_service.generate_feedback(
                    code=code_for_feedback,
                    test_results=test_results,
                    requirements=assignment.requirements or [],
                )
        except Exception:
            ai_feedback = {
                "summary": "Feedback unavailable.",
                "strengths": [],
                "improvements": [],
                "hints": [],
            }

        return {"score": score, "test_results": test_results, "ai_feedback": ai_feedback}

    def _code_for_feedback(self, submission, atype):
        if atype in ("python", "sql"):
            return submission.code or ""
        if atype == "react":
            files = submission.files or {}
            return files.get("/App.js", "") or (list(files.values())[0] if files else "")
        if atype == "html_css":
            files = submission.files or {}
            html = files.get("html", submission.code or "")
            css = files.get("css", "")
            return f"<!-- HTML -->\n{html}\n\n<!-- CSS -->\n{css}"
        return submission.code or ""

    def _grade_python(self, submission, assignment):
        try:
            service = Judge0Service()
            return service.execute_code(
                code=submission.code or "",
                language_id=LANGUAGE_ID_PYTHON,
                test_cases=assignment.hidden_tests or [],
            )
        except Judge0Error as e:
            return {
                "passed_tests": 0,
                "total_tests": max(len(assignment.hidden_tests or []), 1),
                "results": [],
                "error": str(e),
            }

    def _grade_sql(self, submission, assignment):
        db_setup = (assignment.starter_code or {}).get("db_setup", "") or ""
        query = (submission.code or "").strip()
        hidden_tests = assignment.hidden_tests or []
        if not query:
            return {"passed_tests": 0, "total_tests": 1, "results": [{"name": "SQL", "passed": False, "error": "Empty query"}], "error": "Empty query"}

        try:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            if db_setup:
                conn.executescript(db_setup)
            cursor = conn.execute(query)
            keys = [d[0] for d in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            conn.close()
            actual = _rows_to_comparable(rows, keys)
        except Exception as e:
            return {"passed_tests": 0, "total_tests": 1, "results": [{"name": "SQL", "passed": False, "error": str(e)}], "error": str(e)}

        if not hidden_tests:
            return {"passed_tests": 1 if actual else 0, "total_tests": 1, "results": [{"name": "SQL", "passed": bool(actual), "rows": actual}]}
        expected_raw = hidden_tests[0].get("expected_output")
        if isinstance(expected_raw, list):
            expected = expected_raw
        else:
            expected = [expected_raw] if expected_raw is not None else []
        passed = actual == expected
        return {
            "passed_tests": 1 if passed else 0,
            "total_tests": 1,
            "results": [{"name": "SQL", "passed": passed, "expected": expected, "actual": actual}],
        }

    def _grade_react(self, submission, assignment):
        files = submission.files or {}
        code = files.get("/App.js", "") or (list(files.values())[0] if files else "")
        requirements = assignment.requirements or []
        if not requirements:
            return {"passed_tests": 0, "total_tests": 0, "results": []}
        results = []
        for req in requirements:
            keywords = req.split()[:3]
            check = any(kw in code for kw in keywords) if keywords else False
            results.append({"name": req, "passed": check})
        passed_tests = sum(1 for r in results if r["passed"])
        return {"passed_tests": passed_tests, "total_tests": len(results), "results": results}

    def _grade_html_css(self, submission, assignment):
        files = submission.files or {}
        html = files.get("html", submission.code or "")
        if not html.strip():
            return {"passed_tests": 0, "total_tests": max(len(assignment.requirements or []), 1), "results": [], "error": "No HTML content"}
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            return {"passed_tests": 0, "total_tests": 1, "results": [], "error": str(e)}
        requirements = assignment.requirements or []
        if not requirements:
            return {"passed_tests": 0, "total_tests": 0, "results": []}
        results = []
        for req in requirements:
            tag = req.strip().lower().split()[0] if req.strip() else ""
            check = bool(soup.find(tag)) if tag else False
            results.append({"name": req, "passed": check})
        passed_tests = sum(1 for r in results if r["passed"])
        return {"passed_tests": passed_tests, "total_tests": len(results), "results": results}

    def _calculate_score(self, test_results, rubric):
        passed = test_results.get("passed_tests", 0)
        total = test_results.get("total_tests", 1)
        ratio = passed / max(total, 1)
        correctness = rubric.get("correctness", 60)
        return round(ratio * correctness, 1)
