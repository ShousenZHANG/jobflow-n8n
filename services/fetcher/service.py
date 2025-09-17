from fastapi import FastAPI, Query, Body
from pydantic import BaseModel
from typing import List, Optional
from fetch_jobs import fetch_all, load_queries

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
