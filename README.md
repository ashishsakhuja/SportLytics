# SportLytics
Sports analytics and news aggregation platform

## Features
- Automated sports news ingestion from multiple providers (ESPN, NBC Sports, Yahoo Sports)
- Modular ingestion scripts by source and sport
- Structured data storage for analysis and querying
- Easily extensible architecture for adding new leagues or sources

---

## Tech Stack
- Python
- RSS feeds / web ingestion
- PostgreSQL (or SQLite for local testing)
- Virtual environments (`venv`)
- Docker
- Git & GitHub

---

## Getting Started

### Setup Instructions
- Install Docker Desktop (not required for local testing, Dont need to do now)
1. **Clone the repository**
```bash
git clone https://github.com/ashishsakhuja/SportLytics.git
cd SportLytics
cd backend

2. **Start the API server**
```bash
uvicorn app.main:app --reload
### Prerequisites

The API will be available at:
http://127.0.0.1:8000

Interactive docs:
http://127.0.0.1:8000/docs

3. **Run a sample ingestion job**
- python -m app.scripts.ingest_now
This fetches the latest sports news from configured sources and stores it in the database if they arent there already.

4. ** Go to http://127.0.0.1:8000**
To check aggregated news headlines: check hits.txt as it contains copy and paste urls for visualizaiton testing

- Feel free to check different sports here by changing the urls to their keywords: cfb, nfl, nba, nhl, etc



