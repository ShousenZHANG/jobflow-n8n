import os, re, json, hashlib, argparse, logging
from typing import Dict, Any, List
import pandas as pd
from jobspy import scrape_jobs
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# Optional: load .env if python-dotenv is installed (non-fatal if missing)
try:  # lightweight best-effort
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Logging setup
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger("job_fetcher")

# -------- Environment variables & defaults --------
HOURS_OLD        = int(os.getenv("HOURS_OLD", "48"))
RESULTS_WANTED   = int(os.getenv("RESULTS_WANTED", "120"))
LINKEDIN_LOCATION= os.getenv("LINKEDIN_LOCATION", "Sydney, New South Wales, Australia")

SHEET_ID         = os.getenv("SHEET_ID", "")
WORKSHEET        = os.getenv("WORKSHEET", "jobflow")
GOOGLE_CREDS     = os.getenv("GOOGLE_CREDS_PATH", "./credentials.json")

SEEN_PATH        = os.getenv("SEEN_PATH", "./history/seen.json")

# Control whether title must contain one of the query phrases
TITLE_INCLUDE_FROM_QUERIES = os.getenv("TITLE_INCLUDE_FROM_QUERIES", "0").lower() in {"1","true","yes","on"}
# Control whether to apply description exclusion filters
FILTER_DESCRIPTION_DEFAULT = os.getenv("FILTER_DESCRIPTION", "1").lower() in {"1","true","yes","on"}

# Default queries used if none are provided externally
DEFAULT_QUERIES = [
    '"junior software engineer"',
    '"software engineer"',
    '"software developer"',
    '"java developer"',
    '"devops engineer"',
    '"devops developer"',
    '"it support"',
    '"full stack developer"',
    '"full stack engineer"'
]

REQUIRED_BASE = ["id","site","job_url","title","company","location","job_type","job_level","description"]

# Title filtering patterns (exclude)
TITLE_EXCLUDE_PAT = re.compile(
    r'(?i)\b('
    r'senior|sr\.?|lead|principal|architect|manager|head|director'
    r')\b'
)
# Description exclusion patterns
EXCLUDE_EXP_YEARS_RE = re.compile(
    r'(?i)\b(?:[5-9]|1\d|2\d|3\d)\s*(?:\+|-\s*\d+)?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)\b'
)
EXCLUDE_RIGHTS_RE = re.compile(
    r'(?i)\b(?:'
    r'permanent\s+resident|permanent\s+residency|PR\s*(?:only|required)?|'
    r'citizen|citizenship|australian\s+citizen|au\s+citizen|nz\s+citizen|'
    r'baseline\s+clearance|NV1|NV2|security\s+clearance|'
    r'must\s+have\s+(?:full\s+)?work(?:ing)?\s+rights|'
    r'sponsorship\s+not\s+available|no\s+sponsorship'
    r')\b'
)

def normalize_url(u: str) -> str:
    if not isinstance(u, str) or not u:
        return ""
    p = urlparse(u)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not k.lower().startswith("utm_") and k.lower() not in {"fbclid","gclid"}]
    p2 = p._replace(netloc=p.netloc.lower(), query=urlencode(q), fragment="")
    out = urlunparse(p2)
    return out[:-1] if out.endswith("/") else out

def load_queries(cli_queries=None, cli_file: str|None=None) -> list:
    """Load search queries by priority.
    Priority (highest -> lowest):
      1. CLI --query (repeatable)
      2. CLI --queries-file
      3. ENV QUERIES
      4. ENV QUERIES_FILE
      5. DEFAULT_QUERIES
    ENV QUERIES can be separated by | or ,.
    File handling:
      *.json => JSON array
      otherwise => line-based (ignores blank lines and lines starting with #)
    Returns a de-duplicated list preserving order.
    """
    result: List[str] = []
    def add(seq):
        for x in seq:
            x2 = x.strip()
            if x2 and x2 not in result:
                result.append(x2)
    # CLI repeated queries
    if cli_queries:
        add(cli_queries)
    # File from CLI
    file_path = cli_file
    # ENV QUERIES only if no CLI queries
    env_queries_raw = os.getenv("QUERIES", "") if not cli_queries else ""
    # ENV QUERIES_FILE only if no CLI file
    if not file_path:
        file_path = os.getenv("QUERIES_FILE", "")
    # Load file
    if file_path and os.path.isfile(file_path):
        try:
            if file_path.lower().endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    add([str(i) for i in data])
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = [ln.rstrip("\n") for ln in f]
                add([ln for ln in lines if ln.strip() and not ln.strip().startswith('#')])
        except Exception as e:
            logger.warning("Failed to read queries file %s: %s", file_path, e)
    # Parse ENV QUERIES
    if env_queries_raw and not cli_queries:
        parts = [p for chunk in env_queries_raw.split('|') for p in chunk.split(',')]
        add(parts)
    # Fallback
    if not result:
        add(DEFAULT_QUERIES)
    return result

def fetch_site(site: str, location: str, queries: list, extra_kwargs=None, hours_old: int|None=None, results_wanted: int|None=None) -> pd.DataFrame:
    dfs: List[pd.DataFrame] = []
    extra_kwargs = extra_kwargs or {}
    h = hours_old if hours_old is not None else HOURS_OLD
    rw = results_wanted if results_wanted is not None else RESULTS_WANTED
    for term in queries:
        try:
            df = scrape_jobs(
                site_name=[site],
                search_term=term,
                location=location,
                hours_old=h,
                results_wanted=rw,
                verbose=0,
                **extra_kwargs
            )
        except Exception as e:
            logger.error("scrape_jobs failed term=%s site=%s error=%s", term, site, e)
            continue
        if df is None or df.empty:
            continue
        # Remove all-NA columns to avoid future concat dtype warnings
        df = df.loc[:, df.notna().any(axis=0)]
        df["source_query"] = term
        dfs.append(df)
    dfs = [d for d in dfs if d is not None and not d.empty]
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True, sort=False)

def _build_query_phrases(queries: list) -> list:
    """Return normalized phrases (lowercase, stripped quotes) used for include matching."""
    phrases = []
    for q in queries or []:
        if not q:
            continue
        q2 = q.strip().strip('"').strip("'")
        if q2:
            phrases.append(q2.lower())
    return phrases

def filter_title(df: pd.DataFrame, queries: list, enforce_include: bool=False) -> pd.DataFrame:
    """Apply title exclusion filter and optional inclusion based on queries.
    Steps:
      1. Exclude titles matching TITLE_EXCLUDE_PAT.
      2. If enforce_include=True: keep only rows whose title contains ANY full query phrase (case-insensitive) after stripping quotes.
    """
    if df.empty:
        return df
    t = df["title"].fillna("")
    exc = t.apply(lambda s: bool(TITLE_EXCLUDE_PAT.search(s)))
    out = df[~exc].copy()
    if enforce_include:
        phrases = _build_query_phrases(queries)
        if phrases:
            low = out["title"].str.lower()
            mask = low.apply(lambda s: any(p in s for p in phrases))
            out = out[mask].copy()
    return out

def keep_required(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "job_type" not in df.columns and "employment_type" in df.columns:
        df["job_type"] = df["employment_type"]
    if "job_level" not in df.columns and "seniority_level" in df.columns:
        df["job_level"] = df["seniority_level"]
    if "id" not in df.columns:
        df["id"] = df.get("job_url","").fillna("").apply(lambda u: hashlib.md5(u.encode()).hexdigest() if u else "")
    for c in REQUIRED_BASE:
        if c not in df.columns:
            df[c] = ""
    return df[REQUIRED_BASE].fillna("")

def filter_description(df: pd.DataFrame) -> pd.DataFrame:
    if "description" not in df.columns:
        return df
    desc = df["description"].fillna("")
    years = desc.str.contains(EXCLUDE_EXP_YEARS_RE, na=False)
    rights = desc.str.contains(EXCLUDE_RIGHTS_RE, na=False)
    return df[~(years | rights)].copy()

def load_seen(path: str) -> set:
    if not os.path.isfile(path):
        return set()
    try:
        return set(json.load(open(path, "r", encoding="utf-8")))
    except Exception:
        return set()

def save_seen(path: str, seen: set):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)

def append_sheet(df: pd.DataFrame, sheet_id: str, worksheet: str, creds_path: str):
    if not sheet_id or not os.path.isfile(creds_path) or df.empty:
        return "skip"
    import gspread
    gc = gspread.service_account(filename=creds_path)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet, rows="2000", cols="30")
    vals = ws.get_all_values()
    header = vals[0] if vals else []
    needed = ["job_url","title","company","location","job_type","job_level","applied","status"]
    if not vals:
        ws.append_row(needed)
        header = needed
    out = df.copy()
    for c in needed:
        if c not in out.columns:
            out[c] = ""
    out = out[needed].fillna("")
    def make_hyper(url, title):
        if not url:
            return title or ""
        t = (title or "").replace('"','""')
        return f'=HYPERLINK("{url}","{t}")'
    out["title"] = out.apply(lambda r: make_hyper(r["job_url"], r["title"]), axis=1)
    existing_urls = set()
    if header and "job_url" in header:
        url_idx = header.index("job_url")
        for r in vals[1:]:
            if len(r)>url_idx and r[url_idx]:
                existing_urls.add(normalize_url(r[url_idx]))
    out["__key__"] = out["job_url"].map(normalize_url)
    new_df = out[~out["__key__"].isin(existing_urls)]
    if new_df.empty:
        return "no_new"
    rows = new_df.drop(columns=["__key__"]).values.tolist()
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    try:
        ws.set_basic_filter()
        ws.freeze(rows=1)
    except Exception:
        pass
    return f"added_{len(rows)}"

# Unified response helper
def _empty_response(queries: List[str], return_queries: bool) -> Dict[str, Any]:
    base = {"new_count": 0, "sheet_result": None, "items": []}
    if return_queries:
        base["queries"] = queries
    return base

def fetch_all(update_sheet: bool=False,
              queries: list|None=None,
              location: str|None=None,
              hours_old: int|None=None,
              results_wanted: int|None=None,
              reset_seen: bool=False,
              return_queries: bool=False,
              include_from_queries: bool|None=None,
              filter_description_flag: bool|None=None) -> Dict[str, Any]:
    """Fetch LinkedIn job posts with filtering and optional Google Sheet append.
    Args mirror earlier version plus:
      filter_description_flag: override whether to apply description exclusion.
    """
    if queries is None:
        queries = load_queries()
    use_location = location or LINKEDIN_LOCATION
    enforce_include = TITLE_INCLUDE_FROM_QUERIES if include_from_queries is None else include_from_queries
    apply_desc_filter = FILTER_DESCRIPTION_DEFAULT if filter_description_flag is None else filter_description_flag

    if reset_seen and os.path.isfile(SEEN_PATH):
        try:
            os.remove(SEEN_PATH)
            logger.info("Seen cache reset")
        except Exception as e:
            logger.warning("Failed to remove seen cache: %s", e)

    logger.info("Fetching site=linkedin queries=%d location='%s' hours_old=%s results_wanted=%s include=%s desc_filter=%s", len(queries), use_location, hours_old or HOURS_OLD, results_wanted or RESULTS_WANTED, enforce_include, apply_desc_filter)

    lk = fetch_site("linkedin", use_location, queries, {"linkedin_fetch_description": True}, hours_old=hours_old, results_wanted=results_wanted)
    df = lk.copy() if not lk.empty else pd.DataFrame(columns=REQUIRED_BASE)
    if df.empty:
        return _empty_response(queries, return_queries)

    before = len(df)
    df = filter_title(df, queries, enforce_include=enforce_include)
    after_title = len(df)
    df = keep_required(df)
    if "job_url" in df.columns:
        df["job_url_norm"] = df["job_url"].map(normalize_url)
    else:
        df["job_url_norm"] = ""
    df = df.drop_duplicates(subset=["job_url_norm","id"])
    after_dedupe = len(df)
    if apply_desc_filter:
        df = filter_description(df)
    after_desc = len(df)

    # Cross-run dedup
    seen = load_seen(SEEN_PATH)
    mask_new = ~df["job_url_norm"].isin(seen)
    df_new = df[mask_new].copy()
    after_seen = len(df_new)

    if df_new.empty:
        logger.info("No new jobs (title_filtered=%d deduped=%d desc_filtered=%d new=%d)", after_title, after_dedupe, after_desc, after_seen)
        return _empty_response(queries, return_queries)

    new_keys = [k for k in df_new["job_url_norm"].tolist() if k]
    seen.update(new_keys)
    save_seen(SEEN_PATH, seen)

    sheet_result = append_sheet(df_new, SHEET_ID, WORKSHEET, GOOGLE_CREDS) if update_sheet else None

    items = df_new[["job_url","title","company","location","job_type","job_level","description"]].to_dict(orient="records")
    out: Dict[str, Any] = {
        "new_count": len(df_new),
        "sheet_result": sheet_result,
        "items": items,
        "meta": {
            "fetched_raw": before,
            "after_title_filter": after_title,
            "after_row_dedupe": after_dedupe,
            "after_description_filter": after_desc if apply_desc_filter else after_dedupe,
            "new_after_seen": after_seen,
            "include_from_queries": enforce_include,
            "description_filter_applied": apply_desc_filter
        }
    }
    if return_queries:
        out["queries"] = queries
    return out

def main():
    parser = argparse.ArgumentParser(description="Fetch LinkedIn jobs and optionally update Google Sheet.")
    parser.add_argument("--update-sheet", action="store_true", help="Append new jobs into Google Sheet")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--query", action="append", help="Add one search query (repeatable)")
    parser.add_argument("--queries-file", help="Load queries from file (.json array or line-based text)")
    parser.add_argument("--location", help="Override location")
    parser.add_argument("--hours-old", type=int, help="Override time window in hours")
    parser.add_argument("--results-wanted", type=int, help="Override results per query")
    parser.add_argument("--reset-seen", action="store_true", help="Clear dedupe cache before fetching")
    parser.add_argument("--return-queries", action="store_true", help="Include queries list in output")
    parser.add_argument("--include-from-queries", action="store_true", help="Require title to contain at least one query phrase (overrides env)")
    parser.add_argument("--no-desc-filter", action="store_true", help="Disable description exclusion filtering")
    args = parser.parse_args()
    queries = load_queries(cli_queries=args.query, cli_file=args.queries_file)
    result = fetch_all(update_sheet=args.update_sheet,
                       queries=queries,
                       location=args.location,
                       hours_old=args.hours_old,
                       results_wanted=args.results_wanted,
                       reset_seen=args.reset_seen,
                       return_queries=args.return_queries,
                       include_from_queries=args.include_from_queries,
                       filter_description_flag= not args.no_desc_filter)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"New: {result['new_count']}, Sheet: {result['sheet_result']}")

if __name__ == "__main__":
    main()
