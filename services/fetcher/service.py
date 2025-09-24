from fastapi import FastAPI, Query, Body
from pydantic import BaseModel
from typing import List, Optional
from fetch_jobs import fetch_all
import os
# import resolved creds path from fetch_jobs
from fetch_jobs import GOOGLE_CREDS as RESOLVED_GOOGLE_CREDS

app = FastAPI(title="JobFetcher Service")

class FetchOptions(BaseModel):
    update_sheet: bool = False
    queries: Optional[List[str]] = None
    location: Optional[str] = None
    hours_old: Optional[int] = None
    results_wanted: Optional[int] = None
    reset_seen: bool = False
    return_queries: bool = False
    include_from_queries: Optional[bool] = None  # enforce title contains a query phrase
    filter_description: Optional[bool] = None    # control description exclusion filtering

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/debug/env")
def debug_env():
    sheet_id = os.getenv("SHEET_ID", "")
    worksheet = os.getenv("WORKSHEET", "")
    creds = os.getenv("GOOGLE_CREDS_PATH", "")
    exists = os.path.isfile(creds) if creds else False
    resolved = RESOLVED_GOOGLE_CREDS
    resolved_exists = os.path.isfile(resolved) if resolved else False
    # mask sheet id for display safety
    def mask(s: str):
        return s if not s else (s[:4] + "***" + s[-4:] if len(s) > 8 else "***")
    return {
        "SHEET_ID": mask(sheet_id),
        "WORKSHEET": worksheet,
        "GOOGLE_CREDS_PATH": creds,
        "creds_exists": exists,
        "resolved_creds_path": resolved,
        "resolved_creds_exists": resolved_exists,
        "cwd": os.getcwd(),
    }

@app.get("/fetch")
def fetch_get(
    update_sheet: bool = Query(False),
    query: List[str] = Query(None),
    location: str | None = Query(None),
    hours_old: int | None = Query(None),
    results_wanted: int | None = Query(None),
    reset_seen: bool = Query(False),
    return_queries: bool = Query(False),
    include_from_queries: bool | None = Query(None, description="Require title to contain at least one query phrase"),
    filter_description: bool | None = Query(None, description="Apply description exclusion filtering (override env)")
):
    queries = query if query else None
    return fetch_all(update_sheet=update_sheet,
                     queries=queries,
                     location=location,
                     hours_old=hours_old,
                     results_wanted=results_wanted,
                     reset_seen=reset_seen,
                     return_queries=return_queries,
                     include_from_queries=include_from_queries,
                     filter_description_flag=filter_description)

@app.post("/fetch")
def fetch_post(opts: FetchOptions = Body(...)):
    queries = opts.queries if opts.queries else None
    return fetch_all(update_sheet=opts.update_sheet,
                     queries=queries,
                     location=opts.location,
                     hours_old=opts.hours_old,
                     results_wanted=opts.results_wanted,
                     reset_seen=opts.reset_seen,
                     return_queries=opts.return_queries,
                     include_from_queries=opts.include_from_queries,
                     filter_description_flag=opts.filter_description)
