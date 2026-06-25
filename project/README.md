# Notification Module — Deployment & Usage Guide
# ANO VO "Humanitarian University"

---

## Table of Contents

1. Project Structure
2. Prerequisites
3. Installation (Linux)
4. Installation (Windows)
5. Configuration
6. Running the Application
7. Running the Worker
8. Verifying Functionality via Swagger
9. Test Notification Payloads
10. Database Notes


---

## 1. Project Structure

```
notification_module/
|
|-- main.py               # FastAPI app, all HTTP endpoints, lifespan manager
|-- models.py             # Pydantic schemas + SQLAlchemy ORM models
|-- database.py           # Async engine, session factory, schema init
|-- config.py             # Centralised settings loaded from .env
|-- redis_queue.py        # Redis FIFO queue, worker loop, retry with backoff
|-- send_notification.py  # Channel routing, EmailSender, VKSender, GatewayClient
|-- create_content.py     # Jinja2 content builder, default templates
|-- worker.py             # Standalone worker process entry point
|-- requirements.txt      # Python dependencies
|-- .env.example          # Environment variable reference
|-- .env                  # Your local config (created by you, not in VCS)
|
|-- templates/            # Jinja2 templates (auto-created on first startup)
|   |-- new_assignment_email.html
|   |-- new_assignment_email.txt
|   |-- new_assignment_vk.txt
|   |-- deadline_student_email.html
|   |-- deadline_student_email.txt
|   |-- deadline_student_vk.txt
|   |-- deadline_teacher_email.html
|   |-- deadline_teacher_email.txt
|   |-- deadline_teacher_vk.txt
|   |-- review_result_email.html
|   |-- review_result_email.txt
|   |-- review_result_vk.txt
|
|-- logs/                 # Log files (auto-created)
    |-- app.log
    |-- worker.log
```

---

## 2. Prerequisites

| Requirement    | Version      | Notes                                      |
|----------------|--------------|--------------------------------------------|
| Python         | 3.10 or 3.11 | 3.12 also supported                        |
| Redis          | 6.x or 7.x   | Must be running before starting the app    |
| (Optional) PostgreSQL | 14+  | Only needed for production; SQLite default |

---

## 3. Installation — Linux / macOS

```bash
# 1. Clone or copy the project directory
cd notification_module

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install and start Redis (Debian/Ubuntu example)
sudo apt-get update && sudo apt-get install -y redis-server
sudo systemctl start redis-server
# Verify:
redis-cli ping   # should return PONG

# 5. Create your configuration file
cp .env.example .env
# Edit .env with your SMTP, VK, and database settings

# 6. Create the logs directory
mkdir -p logs
```

---

## 4. Installation — Windows

```powershell
# 1. Open PowerShell in the project directory

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Redis for Windows
# Option A: Use the MSI from https://github.com/microsoftarchive/redis/releases
# Option B: Use WSL2 (recommended): wsl --install, then follow Linux steps inside WSL.
# Option C: Use Docker Desktop: docker run -d -p 6379:6379 redis:7

# Verify Redis is reachable:
# redis-cli.exe ping   (or telnet 127.0.0.1 6379)

# 5. Create your configuration file
copy .env.example .env
# Edit .env with Notepad or VS Code

# 6. Create the logs directory
mkdir logs
```

---

## 5. Configuration

Edit `.env` (copy from `.env.example`). Minimum required for a working prototype:

```ini
# Prototype defaults (SQLite + Redis on localhost, no email/VK credentials)
DATABASE_URL=sqlite+aiosqlite:///./notifications.db
REDIS_URL=redis://localhost:6379/0
```

For email delivery, set:
```ini
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USERNAME=your@yandex.ru
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your@yandex.ru
```

For VK delivery, set:
```ini
VK_API_TOKEN=vk1.a.your_token_here
VK_GROUP_ID=123456789
```

When credentials are absent, the module operates in stub mode: notifications
are logged but not actually sent. This allows full end-to-end testing of the
queue, retry logic, and database persistence without external dependencies.

---

## 6. Running the Application (API Server)

### Linux / macOS
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Windows
```powershell
venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

The API will be available at:
- Swagger UI:  http://localhost:8001/docs
- ReDoc:       http://localhost:8001/redoc
- Health:      http://localhost:8001/health

---

## 7. Running the Worker

The worker must be run as a separate process (separate terminal window):

### Linux / macOS
```bash
source venv/bin/activate
python worker.py
```

### Windows
```powershell
venv\Scripts\activate
python worker.py
```

The worker picks tasks from the Redis queue and delivers them via the
configured channels. Without the worker running, tasks accumulate in the
queue with PENDING status and are processed once the worker starts.

---

## 8. Verifying Functionality via Swagger

1. Open http://localhost:8001/docs in a browser.

2. Click the green "POST /notifications/send" endpoint, then "Try it out".

3. Paste one of the example payloads from Section 9 into the request body.

4. Click "Execute".

5. The response will include a `task_id` and status `"pending"`.

6. Check delivery status:
   - Open "GET /notifications/status/{task_id}"
   - Enter the task_id from step 5
   - Execute — status should change to "sent" once the worker processes it

7. View history:
   - Open "GET /notifications/history"
   - Leave all filters empty to see all records

---

## 9. Test Notification Payloads

### 9.1 New Assignment (for student)

```json
{
  "notification_type": "new_assignment",
  "recipient_id": "student-001",
  "channel": "all",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Implementation of a Sorting Algorithm",
    "topic": "Algorithms and Data Structures",
    "deadline": "2025-01-20T23:59:00"
  },
  "student": {
    "full_name": "Ivanov Ivan Ivanovich",
    "group": "PI-201",
    "course": 2,
    "email": "student@example.com",
    "vk_user_id": "12345678"
  }
}
```

### 9.2 Deadline Reminder (for student)

```json
{
  "notification_type": "deadline_student",
  "recipient_id": "student-001",
  "channel": "email",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Implementation of a Sorting Algorithm",
    "topic": "Algorithms and Data Structures",
    "deadline": "2025-01-20T23:59:00"
  },
  "student": {
    "full_name": "Ivanov Ivan Ivanovich",
    "group": "PI-201",
    "course": 2,
    "email": "student@example.com"
  }
}
```

### 9.3 Deadline Summary (for instructor)

```json
{
  "notification_type": "deadline_teacher",
  "recipient_id": "teacher-001",
  "channel": "email",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Implementation of a Sorting Algorithm",
    "topic": "Algorithms and Data Structures",
    "deadline": "2025-01-20T23:59:00"
  },
  "teacher": {
    "full_name": "Petrov Petr Petrovich",
    "email": "teacher@example.com"
  },
  "submission_summary": {
    "submitted": [
      "Ivanov Ivan Ivanovich",
      "Sidorova Maria Alexeyevna"
    ],
    "not_submitted": [
      "Kuznetsov Dmitry Olegovich",
      "Volkova Anastasia Sergeyevna"
    ]
  }
}
```

### 9.4 Assignment Graded (for student)

```json
{
  "notification_type": "review_result",
  "recipient_id": "student-001",
  "channel": "all",
  "assignment": {
    "assignment_id": "asgn-42",
    "title": "Implementation of a Sorting Algorithm",
    "topic": "Algorithms and Data Structures",
    "deadline": "2025-01-20T23:59:00",
    "grade": 92.0,
    "max_grade": 100.0,
    "feedback": "Good implementation of QuickSort. The complexity analysis is correct. Add more edge case tests."
  },
  "student": {
    "full_name": "Ivanov Ivan Ivanovich",
    "group": "PI-201",
    "course": 2,
    "email": "student@example.com",
    "vk_user_id": "12345678"
  }
}
```

### 9.5 Update User Settings

```
PUT /notifications/settings/student-001

{
  "email_enabled": true,
  "vk_enabled": false,
  "email_address": "newemail@example.com"
}
```

---

## 10. Database Notes

### SQLite (default, prototype)
No additional setup. The file `notifications.db` is created automatically
in the project directory on first startup.

To inspect the database:
```bash
# Linux
sqlite3 notifications.db "SELECT task_id, status, notification_type FROM notification_records LIMIT 10;"

# Windows (if sqlite3.exe is in PATH)
sqlite3.exe notifications.db "SELECT task_id, status FROM notification_records;"
```

### PostgreSQL (production)
1. Create a database:
```sql
CREATE DATABASE notifications_db;
CREATE USER notifications_user WITH PASSWORD 'secret';
GRANT ALL PRIVILEGES ON DATABASE notifications_db TO notifications_user;
```

2. Update `.env`:
```ini
DATABASE_URL=postgresql+asyncpg://notifications_user:secret@localhost:5432/notifications_db
```

3. Tables are created automatically on startup (SQLAlchemy `create_all`).

---

## 11. Troubleshooting

### Redis connection refused
Ensure Redis is running:
```bash
redis-cli ping          # Linux
redis-cli.exe ping      # Windows
```
If using a non-default port, update `REDIS_URL` in `.env`.

### Email not sending
- Verify SMTP credentials in `.env`.
- For Yandex: enable "App passwords" in account settings and use an app password.
- For Gmail: use an app-specific password (not your account password).
- Check `logs/worker.log` for the exact SMTP error.

### VK messages not sending
- Ensure the community token has the `messages` permission.
- Ensure "Allow messages from community" is enabled in VK community settings.
- The recipient must have started a conversation with the community bot first.

### Tasks stay PENDING
The worker is not running. Start `python worker.py` in a separate terminal.

### Template errors
Templates are auto-created in `templates/` on first startup. If they are
missing or corrupted, delete the `templates/` directory and restart the
application — they will be regenerated from defaults.
