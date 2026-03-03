# Assignment Automation POC — Django REST Backend

Django REST backend for the Assignment Automation POC. No auth; uses seeded default mentor and student for POC.

## Requirements

- Python 3.10+
- PostgreSQL (optional; SQLite is used if `DATABASE_URL` is not set)
- Dependencies: see [requirements.txt](requirements.txt)

## Setup

1. Create and activate a virtualenv (optional but recommended).

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in values:
   - **Required**: `SECRET_KEY`
   - **AI generation**: `GEMINI_API_KEY` (for POST /api/assignments/generate/)
   - **Python grading**: `JUDGE0_API_URL` and `JUDGE0_API_KEY` (for running Python code via Judge0)
   - **PostgreSQL** (optional): set `DATABASE_URL`. If unset, SQLite (`db.sqlite3`) is used.

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Seed POC data (creates mentor id=1, student id=2, and sample topics):
   ```bash
   python manage.py seed_poc
   ```

6. Start the server:
   ```bash
   python manage.py runserver
   ```
   Default: http://localhost:8000

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/health/ | Health check |
| GET | /api/topics/ | List topics |
| POST | /api/assignments/generate/ | AI generate assignment (body: topic_ids, difficulty, assignment_type) |
| POST | /api/assignments/ | Create assignment (body: title, assignment_type, difficulty, description, requirements, starter_code, public_tests, hidden_tests, grading_rubric, topic_ids) |
| GET | /api/assignments/ | List mentor assignments |
| GET | /api/assignments/{id}/ | Get assignment detail |
| POST | /api/assignments/{id}/assign/ | Assign to students (body: student_ids) |
| GET | /api/student/assignments/ | List student assignments |
| POST | /api/submissions/ | Submit code (body: assignment_id, code?, files?) |
| GET | /api/submissions/{id}/ | Get submission with score and feedback |
| POST | /api/run-tests/ | Run Python tests without saving (body: code, assignment_id? or test_cases) |

## Example Request Bodies

**POST /api/assignments/generate/**
```json
{
  "topic_ids": [1, 2],
  "difficulty": "easy",
  "assignment_type": "python"
}
```

**POST /api/assignments/** (minimal shape)
```json
{
  "title": "Hello World",
  "assignment_type": "python",
  "difficulty": "easy",
  "description": "Print the input.",
  "requirements": ["Use print and input"],
  "starter_code": {},
  "public_tests": [{"name": "Test 1", "input": "hi", "expected_output": "hi"}],
  "hidden_tests": [{"name": "Hidden", "input": "x", "expected_output": "x"}],
  "grading_rubric": {"correctness": 60, "code_quality": 20, "edge_cases": 20},
  "topic_ids": [1]
}
```

**POST /api/assignments/{id}/assign/**
```json
{
  "student_ids": [2]
}
```

**POST /api/submissions/** (Python)
```json
{
  "assignment_id": 1,
  "code": "print(input())"
}
```

**POST /api/submissions/** (React)
```json
{
  "assignment_id": 1,
  "files": { "/App.js": "export default function App() { return <div>Hi</div>; }" }
}
```

## POC Notes

- **No auth**: The API uses default mentor (id=1) and student (id=2) from `seed_poc`. All assignment creation is attributed to mentor 1; all submissions are attributed to student 2.
- **CORS**: All origins are allowed for local frontend development (e.g. Next.js on port 3000).

## Manual Testing (Sanity Checks)

1. **GET /api/health/** → 200, `{"status": "ok"}`
2. **GET /api/topics/** → 200, list of topics (after seed)
3. (Optional) **POST /api/assignments/generate/** with valid body and `GEMINI_API_KEY` → 200, generated assignment JSON
4. **POST /api/assignments/** with full body → 201, created assignment
5. **POST /api/assignments/{id}/assign/** with `student_ids: [2]` → 200
6. **GET /api/student/assignments/** → 200, list includes assigned assignment
7. **GET /api/assignments/{id}/** → 200, assignment detail with starter_code
8. **POST /api/submissions/** with assignment_id and code (or files for React) → 201, submission with score, test_results, ai_feedback
9. **GET /api/submissions/{id}/** → 200, same submission with status completed

Optionally test at least one submission per type (python, sql, react, html_css) to confirm GraderRouter and (for Python) Judge0.
