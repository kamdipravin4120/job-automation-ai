# Automated Job Application System

Production-oriented Python workflow for scraping jobs, ranking them with OpenAI embeddings, tailoring ATS-safe resumes with Claude, generating DOCX assets, running semi-automated LinkedIn Easy Apply, and tracking every step in CSV or SQLite.

## Architecture

```text
src/
  scraper/      LinkedIn and Naukri job scraping adapters
  matcher/      OpenAI embedding client and weighted semantic ranking
  resume/       Claude-powered tailoring + ATS-safe DOCX generator
  apply/        Playwright-based LinkedIn Easy Apply workflow
  tracking/     CSV/SQLite persistence + Streamlit dashboard
  orchestrator/ End-to-end pipeline
  utils/        Config, browser helpers, logging, retry, text helpers
main.py         CLI entrypoint
config.yaml     Central configuration
data/profile.json
```

## Features

- Config-driven scraping, matching, resume generation, application, and tracking.
- Modular package layout with clear service boundaries.
- OpenAI embeddings with cosine similarity and weighted scoring.
- Claude-based output generation for tailored resume text, recruiter pitch, and cover letter.
- ATS-safe DOCX generation with a simple single-column layout.
- Playwright browser automation with session reuse, human-like delays, upload support, and multi-step form handling.
- Ordered selector fallback lists for scraper resilience when LinkedIn or Naukri change their markup.
- SQLite or CSV tracking plus a Streamlit dashboard.
- Optional Notion sync for application tracking status reporting.
- Structured logging and retry wrappers for external API calls.

## Setup

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configure API keys.

```bash
cp .env.example .env
```

Set:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `NOTION_API_KEY` if you want local tracking records pushed into Notion

4. Update `data/profile.json` with your real profile details.

5. Review `config.yaml`:

- add or change search queries
- adjust scraping selectors if LinkedIn or Naukri change their DOM
- choose `tracking.mode` as `sqlite` or `csv`
- decide whether final submission should pause for manual review
- confirm `notion.application_tracking_data_source_id` points to your Notion tracking data source

## Usage

Run the full pipeline:

```bash
python3 main.py --config config.yaml pipeline
```

Run without final submission:

```bash
python3 main.py --config config.yaml pipeline --skip-apply
```

Run phase by phase:

```bash
python3 main.py --config config.yaml scrape
python3 main.py --config config.yaml match
python3 main.py --config config.yaml resume
python3 main.py --config config.yaml apply
python3 main.py --config config.yaml sync-notion
```

Launch the dashboard:

```bash
python3 main.py --config config.yaml dashboard
```

Run the unit tests:

```bash
python3 -m unittest discover -s tests -v
```

## Docker

Build the image:

```bash
docker build -t job-automation-ai .
```

Run the pipeline in a container:

```bash
docker run --rm -it --env-file .env -v "$(pwd):/app" job-automation-ai \
  python3 main.py --config config.yaml pipeline --skip-apply
```

Use Docker Compose:

```bash
docker compose run --rm app
docker compose run --rm app python3 -m unittest discover -s tests -v
docker compose up dashboard
```

## Pipeline Flow

1. Scrape jobs from LinkedIn and Naukri using Playwright and selector-driven parsers.
2. Generate OpenAI embeddings for the profile and each job.
3. Score jobs using:
   - description similarity
   - title similarity
   - profile skill overlap
4. Keep the top-ranked matches above the configured threshold.
5. Send the candidate profile plus job description to Claude.
6. Save:
   - ATS-safe tailored resume text
   - recruiter pitch
   - cover letter
   - resume DOCX
7. Reuse the LinkedIn browser session and walk the Easy Apply flow.
8. Track every job state in SQLite or CSV and inspect results in Streamlit.
9. Optionally sync local application records into the configured Notion data source.

## Notes

- The first scraping or apply run will open a browser and wait for you to log in if saved cookies are not available.
- LinkedIn and Naukri markup changes over time. Each selector key in `config.yaml` can now hold an ordered list of fallback selectors, so update the config before changing scraper code.
- The Easy Apply flow defaults to semi-automated behavior by pausing before final submission when `manual_review_required: true`.
- Notion sync is best-effort. If the token or data source access is missing, the local pipeline still runs and logs a warning.
- This project assumes you will use it in line with each platform's terms, rate limits, and account policies.

## Output Locations

- scraped jobs: `artifacts/jobs/jobs.json`
- tailored resumes: `artifacts/resumes/`
- cover letters: `artifacts/covers/`
- recruiter pitches: `artifacts/pitches/`
- tracking DB or CSV: `artifacts/`
- logs: `logs/job_automation.log`
- Notion application tracking data source: configured in `config.yaml`
