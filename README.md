## JobFlow (n8n) - Quick Start

This repo runs n8n and a TeX Live container to automate: fetch jobs → analyze JD → render Cover Letter/CV via LaTeX.

### 1) Prereqs
- Install Docker Desktop and ensure it is running.
- Clone this repo, then copy env:
```bash
cp .env.example .env
```
Edit `.env` (set `N8N_BASIC_AUTH_*` and API keys).

### 2) Start with Docker Compose
```bash
# create named volume (optional; compose will create it automatically)
docker volume create n8n_data

# start services
docker compose up -d

# open n8n UI
# http://localhost:5678
```

### 3) Import the starter workflow
- In n8n UI → Workflows → Import → select `n8n/workflows/jobflow-starter.json`.
- Run once manually to test.

### 4) Templates & configs
- Cover letter: `templates/cover_letter/main.tex`
- CV: `templates/cv/main.tex`
- Profile: `profiles/profile.yaml`
- Search filters: `configs/search.yaml`

To compile manually inside the TeX container:
```bash
docker exec -it texlive sh -lc "cd templates/cover_letter && xelatex main.tex"
```

### 5) Next
- Wire job source (Apify/SerpAPI) and LLM (OpenAI/Anthropic) credentials via n8n → Credentials.
- Add steps: JD parsing, scoring, template rendering, PDF compilation, outputs to `./outputs`.
