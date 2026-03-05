# SportLytics

SportLytics is a full-stack sports analytics platform that ingests historical and live sports data, processes advanced statistics, and visualizes team performance through interactive dashboards.

The platform supports multiple professional sports leagues and provides automated **AI-generated insights** for each visualization.

SportLytics combines:

- Automated sports data ingestion
- Advanced statistical processing
- Interactive visualization dashboards
- AI-generated analytical insights
- News aggregation and enrichment

The goal of the platform is to provide a unified analytics environment where users can explore team performance trends, advanced metrics, and contextual insights across multiple sports.

---

## Frontend

- **Next.js**
- **React**
- **Recharts** for visualizations
- Dynamic dashboards for each sport

## Backend

- **FastAPI**
- REST analytics API
- AI insight generation endpoints

## Database

- **PostgreSQL**
- Managed with **Alembic migrations**
- Stores games, teams, standings, and analytics data

## Data Ingestion

Custom ingestion pipelines populate the database using:

- Sports data APIs
- Historical game records
- Scheduled ingestion scripts

## AI Insight System

A lightweight AI system generates short analytical captions for charts using structured statistical summaries.

Insights are cached to avoid repeated model calls.

---

# Core Features

## Multi-Sport Support

Currently supported leagues:

- NFL
- NBA
- MLB
- NHL

Each sport has its own analytics dashboard.

---

# Analytics Dashboards

Each team dashboard includes advanced visualizations.

## Offensive vs Defensive Performance

Scatter plot showing team scoring vs opponent scoring.

## Rolling Averages

Moving averages showing recent offensive and defensive trends.

## Recent Form

Last-5 vs previous-5 performance comparison.

## Home vs Away Performance

Comparison of scoring margins depending on location.

## Score Distribution

Histogram showing scoring frequency.

## Margin Distribution

Distribution of point differentials across games.

## Close Games

Win/loss results in games decided by small margins.

## Strength of Schedule

Schedule difficulty trends across the season.

## League Scoring Trend

League-wide scoring averages over time.

## League Standings

Current standings snapshot for each conference/division.

---

# AI Generated Insights

Each chart includes an **AI generated insight caption**.

The system works as follows:

1. Statistical summaries are computed locally in the frontend.
2. Only summary statistics are sent to the backend.
3. The backend generates a short explanation.
4. Results are cached to reduce API calls.

Example caption:

> "Buffalo has averaged 31.4 points over the last five games, a 6.2 point increase from their previous five."


---

# System Requirements

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis (optional for caching)

---

# Installation

Clone the repository:

```bash
git clone https://github.com/your-org/sportlytics.git
cd sportlytics

# Backend
```bash
cd backend
python -m venv SportLytics
SportLytics\Scripts\activate or source SportLytics/bin/activate #(Win or Mac)
pip install -r requirements.txt

# Database Setup
Create PostgreSQL database
Set database connection:
Example name: sportshub
Set connection:
DATABASE_URL=postgresql+psycopg2://sportshub:sportshub@127.0.0.1:5432/sportshub

Run db migrations
```bash
alembic upgrade head

This creates the required tables including:
- games
- teams
- standings
- news_items
- ingest_runs

# Data Ingestion
```bash
python -m app.scripts.ingest_nfl --season 2025 --season-type REG
python -m app.scripts.ingest_nba --season 2025
python -m app.scripts.ingest_mlb --from-date 2015-03-24 --to-date 2015-10-01
python -m app.scripts.ingest_nhl --season 2025

# Running Backend
```bash
uvicorn app.main:app --reload

# API runs at: http://localhost:8000

# Frontend
```bash
cd frontend
npm install
npm run dev
