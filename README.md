# SportLytics

SportLytics is a full-stack sports analytics platform that ingests sports data, processes advanced team and game statistics, and delivers interactive dashboards, AI-assisted insights, and community sharing tools across multiple major professional leagues.

The platform is designed to provide a single analytics environment where users can:

- explore team performance trends
- compare recent form and season-long metrics
- analyze schedule difficulty and scoring patterns
- read aggregated sports news
- ask an AI assistant grounded questions about team trends
- generate, download, and share custom visualizations

SportLytics currently supports:

- **NFL**
- **NBA**
- **MLB**
- **NHL**

---

## What SportLytics Includes

SportLytics combines several systems into one platform:

- **multi-sport data ingestion pipelines**
- **PostgreSQL-backed analytics storage**
- **FastAPI analytics and AI endpoints**
- **Next.js frontend dashboards**
- **custom chart builder**
- **AI-generated chart captions**
- **Pulse**, a sports AI assistant for natural-language analytics questions
- **community sharing features** for charts and discussion

The project is built to support both historical backfills and recurring updates for games, news, and team game statistics.

---

# Core Features

## 1. Multi-Sport Analytics Dashboards

Each supported sport has its own dashboard with team-level and league-level analytics.

Available views include:

- offensive vs defensive profile
- rolling scoring averages
- recent form comparisons
- home vs away splits
- score and margin distributions
- close-game performance
- strength of schedule trends
- standings and ranking views
- in-game and advanced stat breakdowns where available

---

## 2. AI-Generated Chart Captions

SportLytics generates short AI captions beneath charts using structured numeric summaries rather than raw full datasets.

This keeps the AI grounded and efficient.

Typical flow:

1. the frontend computes a compact numeric summary from the chart data
2. the backend receives the summary
3. an AI service generates a short explanation
4. the result is cached to reduce repeated model calls

Example output:

> “Buffalo has scored noticeably better over its most recent five games, averaging 6.2 more points than in the prior five-game stretch.”

---

## 3. Pulse AI Assistant

**Pulse** is SportLytics’ AI assistant for sports questions.

Pulse is designed to answer natural-language analytics questions such as:

- “How have the Bills looked in their last five games?”
- “Which teams are trending up defensively?”
- “Compare the Eagles and Cowboys recent form”
- “Who has had the toughest schedule lately?”

Pulse can return:

- structured analytical responses
- confidence-aware narratives
- generated charts when a question is visual in nature
- grounded summaries based on platform data

---

## 4. Custom Builder

The Custom Builder allows users to create their own sports charts using available team and league data.

Users can build views such as:

- team trend lines
- team overlays
- metric-vs-metric comparisons
- season summaries
- custom chart presets
- downloadable chart images
- shareable chart views

---

## 5. News Aggregation

SportLytics ingests and stores sports news content that can be surfaced throughout the platform to provide context around performance, injuries, roster changes, and trending topics.

---

## 6. Community Features

SportLytics includes community functionality for users to share visualizations and participate in conversations around analytics-driven sports discussion.

This includes:

- chart sharing
- community posting
- public-facing discussion surfaces
- user identity and authentication
- premium-aware gated AI experiences

---

# Tech Stack

## Frontend

- **Next.js**
- **React**
- **TypeScript**
- **Tailwind CSS**
- **Recharts**
- **Framer Motion**

## Backend

- **FastAPI**
- **SQLAlchemy**
- **Alembic**
- **Pydantic / pydantic-settings**

## Database / Infrastructure

- **PostgreSQL**
- **Redis** (optional, used for caching where configured)
- **Docker Compose** for local infrastructure

## AI / Insight Layer

- AI-backed chart captioning
- Pulse provider architecture with support for:
  - **Hugging Face**
  - **OpenAI**
- cached AI responses for efficiency

---

# Repository Structure

```text
SportLytics/
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── scripts/
│   │   ├── services/
│   │   ├── models.py
│   │   ├── db.py
│   │   ├── auth.py
│   │   ├── main.py
│   │   └── settings.py
│   ├── alembic/
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── next.config.ts
├── infra/
│   └── docker-compose.yml
└── README.md

```

Local Development Requirements:
 - Python 3.10+
 - Node.js 18+
 - npm
 - Docker Desktop or another Docker runtime
 - PostgreSQL

Recommended:
 - Redis (optional, for AI response caching)
 - AI API keys for OpenAI or Hugging Face if using AI features

Environment Configuration:

Create a file at:

```bash
backend/.env
```

And add the following variables:

```env
ENV=local

DATABASE_URL=postgresql://sportshub:sportshub@127.0.0.1:5433/sportshub
REDIS_URL=redis://localhost:6379/0
SPORTLYTICS_PREMIUM_ADMIN_KEY=
SPORTLYTICS_APP_BASE_URL=http://localhost:3000

PULSE_MODEL_PROVIDER=huggingface
HUGGINGFACE_API_TOKEN=your_huggingface_token_here
HUGGINGFACE_MODEL=mistralai/Mistral-7B-Instruct-v0.3

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_PULSE_MODEL=gpt-4o-mini

PULSE_FALLBACK_PROVIDER=
PULSE_TEMPERATURE=0.35
PULSE_INCLUDE_META=1
```

Adjust values as needed for your local development environment.

Notes: 
 - If you are using the included Docker Compose setup, the database port may be 5433 locally.
 - SESSION_COOKIE_SECURE=False is correct for local HTTP development.
 - If you do not configure AI provider keys, AI-dependent features may fail or degrade locally

Frontend:

```bash
frontend/.env.local
```

```env
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

If you intentionally want your frontend to hit deployed backend, set:
```env
NEXT_PUBLIC_API_BASE=https://api.sportlytics.net
```

Running Sportlytics End-To-End Locally:

```bash
git clone https://github.com/ashishsakhuja/sportlytics.git
cd sportlytics
```
Start local infrastructure (PostgreSQL, Redis):
```bash
cd infra
docker compose up -d
cd ..
```

Set up the backend:
```bash
cd backend
python -m venv .venv
```

Windows Powershell:
```powershell
.venv\Scripts\Activate.ps1
```
```bash
pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.sync_latest --sports nfl,nba,mlb,nhl --days-back 365 --days-forward 3 --nfl-season 2025 --nfl-season-types REG,POST --stats-lookback-days 365 --stats-only-final
```

This sync_latest parameters provided above will run the script for the last 1 season for all sports supported. Change accordingly.

Start the backend server:
```bash
uvicorn app.main:app --reload
```
The backend will run at http://127.0.0.1:8000

Health check:
http://127.0.0.1:8000/healthz

Start the frontend:

Open a second terminal
```bash
cd frontend
npm install
npm run dev
```

The frontend will run at http://localhost:3000

