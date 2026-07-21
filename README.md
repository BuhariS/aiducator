# Aiducator

AI-native Learning Management System (LMS) for AI era.
## Inspiration

Large Language Models (LLMs) have revolutionized education, offering an incredible ability to generate rich academic content at unprecedented speed. However, because LLMs operate on probabilistic patterns, their outputs aren't infallible: they can contain subtle logical flaws, biases, or factual hallucinations.

While AI excels at automating the foundational levels of Bloom’s Taxonomy (remembering and understanding) at scale, the true future of education lies in elevated critical thinking. To safely and effectively leverage AI, learners must develop skills in prompt engineering, critical evaluation, and error detection.

Driven by this vision, I collaborated with **GPT-5.6 Luna** to rapidly prototype **Aiducator**—a modern Learning Management System (LMS) designed to transform how we learn and teach.

### Key Objectives:

* **For Learners:** Shift focus toward higher-order critical thinking by prompting students to analyze, critique, and evaluate AI-generated course content and assessments.
* **For Educators:** Eliminate administrative burn-out. Aiducator automates course creation, assessment design, and learning analytics, freeing up valuable time for teachers to provide personalized mentorship, tailored guidance, and timely instructional adjustments.

## What I Learned

Tools like **Codex** and **GPT-5.6** are profound force multipliers. When guided effectively, they drastically compress the development lifecycle: reducing both the time and cost required to turn high-impact ideas into real-world software that serves humanity.

## How Aiducator Was Built

The development workflow followed an iterative, human-in-the-loop co-creation model:

1. **Problem Definition & Architecture:** I defined the core problem, selected the tech stack, and authored the initial software functional specifications.
2. **AI Architectural Review:** I submitted the specifications to the AI model for critical analysis, stress-testing, and suggestions. I then synthesized these insights to produce a final, optimized blueprint.
3. **Phased Implementation:** I fed the refined specifications into Codex powered by GPT-5.6 Luna. Codex structured the project into logical execution phases and handled the heavy lifting—from initial scaffold drafting to test execution.
4. **Co-Creation & Refinement:** Working phase-by-phase alongside Codex, I evaluated the generated code, refined components, debugged edge cases, and managed version control commits and remte update.

## Challenges

The sheer speed and capability of Codex and GPT-5.6 presented a unique challenge: **managing scope and abstraction**. Because the AI could generate complex features so rapidly, I was at times stuck in the implementation details.

## Next Steps
To build upon Aiducator's foundational LMS capabilities, future development will expand beyond text and traditional assessments into fully multimodal learning environments:

- AI-Generated Academic Videos: Integrate video synthesis tools to automatically produce tailored bite-sized lecture clips and visual walkthroughs for complex topics.

- Automated Educational Infographics: Expand generative workflows to output structured visual summaries, process diagrams, and data charts that aid visual learners.

- Interactive Science & Physics Simulations: Enable real-time generation of interactive sandbox environments and simulations, allowing students to manipulate variables directly to deepen conceptual understanding.

## Local setup

# 🚀 Run Aiducator Locally

This guide walks you through setting up **Aiducator** from scratch for both **development** and **AI-powered course generation**.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

* Python **3.12+**
* [uv](https://docs.astral.sh/uv/)
* Node.js **18+**
* npm
* Docker *(optional, for Redis/Celery background processing)*
* An OpenAI API key *(required for AI course generation)*

---

# ⚡ Quick Start

```bash
git clone <repo-url>
cd aiducator

uv sync

npm install
npm run build

cp .env.example .env

uv run python manage.py migrate

uv run python manage.py runserver
```

Open:

```
http://127.0.0.1:8000
```

---

# 📦 Installation

## 1. Clone the Repository

```bash
git clone <repo-url>
cd aiducator
```

---

## 2. Install Backend Dependencies

```bash
uv sync
```

---

## 3. Install Frontend Dependencies

```bash
npm install
npm run build
```

---

## 4. Configure Environment Variables

Create your environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
DJANGO_DEBUG=1

AI_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-real-key
OPENAI_MODEL=gpt-5.6

# Run Celery tasks synchronously (recommended for local development)
CELERY_TASK_ALWAYS_EAGER=1
```

### Notes

* SQLite is the default database for local development.
* Never commit your `.env` file or expose your API key.
* If you need a new API key, generate one from the OpenAI dashboard.

---

## 5. Run Database Migrations

```bash
uv run python manage.py migrate
```

---

## 6. (Optional) Load Demo Course

If you'd like sample content to explore the application quickly:

```bash
uv run python manage.py seed_python_course
```

> Skip this step if you want to create courses entirely with AI.

---

## 7. Start the Development Server

```bash
uv run python manage.py runserver
```

Visit:

```
http://127.0.0.1:8000
```

---

# 👩‍🏫 Teacher Workflow

Create a teacher account:

```
http://127.0.0.1:8000/accounts/signup/teacher/
```

After signing in:

1. Open **Course Studio**
2. Select **Generate with AI**
3. Fill in the course information
4. Submit generation
5. Review the generated content
6. Validate and publish the course

With

```env
CELERY_TASK_ALWAYS_EAGER=1
```

AI generation runs immediately in the request without requiring Redis or Celery.

---

# 👨‍🎓 Student Workflow

Create a student account:

```
http://127.0.0.1:8000/accounts/signup/student/
```

Then:

* Browse available courses
* Enroll in a published course
* Complete lessons
* Take assessments
* Receive AI feedback
* Track learning progress

---

# ⚙️ Running Background Workers (Optional)

For a production-like experience with asynchronous AI generation and grading:

Start Redis:

```bash
docker compose up -d redis
```

Disable eager execution:

```env
CELERY_TASK_ALWAYS_EAGER=0
```

Start a Celery worker:

```bash
uv run celery -A config worker --loglevel=INFO
```

Keep the Django server running in a separate terminal.

---

# 👑 Django Admin (Optional)

Create an administrator account:

```bash
uv run python manage.py createsuperuser
```

Access the admin panel:

```
http://127.0.0.1:8000/admin/
```

---

# 🩺 Verify Installation

Run Django's system checks:

```bash
uv run python manage.py check
```

---

# 🔧 Troubleshooting

### OpenAI API key must be set

Your `.env` file is missing:

```env
OPENAI_API_KEY=...
```

Restart the Django server after updating `.env`.

---

### 401 Unauthorized

Your API key is invalid, revoked, or incorrectly copied.

---

### Quota or Billing Error

Your OpenAI project does not currently have available API usage or billing configured.

---

### AI Generation Doesn't Run

If using background workers, ensure:

* Redis is running
* Celery worker is running
* `CELERY_TASK_ALWAYS_EAGER=0`

For local development, simply use:

```env
CELERY_TASK_ALWAYS_EAGER=1
```

---

# 🔄 Reset Local Database

## Keep a Backup

```bash
mv db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d%H%M%S)
```

Recreate the database:

```bash
uv run python manage.py migrate
```

(Optional)

```bash
uv run python manage.py seed_python_course
```

---

# 📁 Project Structure

```text
aiducator/
├── config/
├── apps/
├── frontend/
├── templates/
├── static/
├── media/
├── manage.py
├── package.json
├── pyproject.toml
├── docker-compose.yml
└── .env.example
```



## 🎉 You're Ready!

Your Aiducator instance is now ready.

Next steps:

1. Create a **Teacher** account.
2. Generate an AI-powered course.
3. Publish the course.
4. Create a **Student** account.
5. Enroll and experience the complete learning workflow.
