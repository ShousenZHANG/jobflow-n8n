# JobFlow – Automated Job Data Fetcher (Python / FastAPI)

## Overview

JobFlow is a **lightweight backend service** built with **Python and FastAPI** for fetching, processing, and exporting job data.

The project is intentionally kept **simple and backend-focused**:

It is designed to be easy to run locally, easy to reason about, and suitable as a **clean engineering portfolio project**.

---

## Tech Stack

* **Python 3.10+**
* **FastAPI** – REST API
* **Uvicorn** – ASGI server
* **Virtualenv (.venv)** – dependency isolation

---

## Project Structure

```
jobflow/
├─ services/
│  └─ fetcher/
│     ├─ service.py        # FastAPI application entrypoint
│     ├─ requirements.txt  # Python dependencies
│     ├─ .env              # Environment variables (not committed)
│     └─ .venv/             # Local virtual environment
└─ README.md
```

---

## Prerequisites

Make sure you have the following installed:

* **Python 3.10 or later**
* **pip** (comes with Python)
* **Windows PowerShell** (commands below assume Windows)

---

## Local Setup

### 1. Navigate to the fetcher service

```powershell
cd D:\jobflow-n8n\services\fetcher
```

---

### 2. Create and activate virtual environment (first time only)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

You should see `(.venv)` at the beginning of your terminal prompt.

---

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

---

### 4. Configure environment variables

Create a `.env` file in `services/fetcher/`.

Example:

```env
TZ=Australia/Sydney
```

> Add any API keys or runtime configuration here. The `.env` file is intentionally excluded from version control.

---

## Running the Service

Start the FastAPI application using Uvicorn:

```powershell
uvicorn service:app --host 0.0.0.0 --port 8000 --env-file .env
```

If successful, you should see output similar to:

```
Uvicorn running on http://0.0.0.0:8000
```

---

## API Documentation

FastAPI provides automatic interactive documentation.

Once the service is running, open:

* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

These pages allow you to inspect endpoints and test requests directly in the browser.

---

## Development Notes

* This project intentionally avoids unnecessary infrastructure to keep the runtime and setup minimal.
* The service can later be containerised or integrated into a larger system if required.

---

## Why This Design

This repository demonstrates:

* Clear separation of concerns
* A clean Python backend setup
* Practical use of FastAPI for service development
* Sensible dependency and environment management

It reflects an **engineering-first approach**, favouring clarity and maintainability over unnecessary complexity.

---

## License

This project is provided for learning and demonstration purposes.
