# Reddit Mortgage Lead Scraper

A continuously running Reddit scraper that monitors 20 finance/real estate subreddits for mortgage-related posts and comments, stores them in a local CSV, and syncs to Google Sheets. A live Flask web dashboard displays the collected leads in real time.

---

## Architecture Overview

```
scraper.py  ──→  leads.csv (primary data store)
                      │
            dashboard.py reads CSV every 5s
                      │
            Browser at http://localhost:5000
                      │
sync_csv_to_sheets.py ──→  Google Sheets (manual sync utility)
```

**Three main components:**
1. **`scraper.py`** — Continuous Reddit crawler. Writes Posts + Comments to `leads.csv` and Google Sheets.
2. **`dashboard.py`** — Flask web app. Reads `leads.csv` directly and serves a live auto-refreshing HTML dashboard.
3. **`sync_csv_to_sheets.py`** — One-shot utility to push the entire local CSV to Google Sheets (run manually when needed).

---

## How to Run

### Install dependencies (first time only)
```bash
python -m pip install flask gspread requests beautifulsoup4 python-dotenv
```

### Start the scraper
```bash
python scraper.py > scraper.log 2>&1 &
```

### Start the dashboard
```bash
python dashboard.py > dashboard.log 2>&1 &
```

Then open **http://localhost:5000** in a browser.

### Sync CSV → Google Sheets (manual, run anytime)
```bash
python sync_csv_to_sheets.py
```

---

## Required Files (not in git — must be present locally)

| File | Purpose |
|---|---|
| `credentials.json` | Google Cloud service account key for Sheets API |
| `.env` | Reddit API credentials (CLIENT_ID, CLIENT_SECRET, USER_AGENT) |
| `leads.csv` | Primary data store — created/appended by scraper at runtime |
| `seen_ids.json` | Tracks already-scraped post IDs to avoid duplicates — auto-created |
| `post_rows.json` | Maps post IDs to their row positions in Google Sheets — auto-created |

### .env format
```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent_string
```

### credentials.json
Google Cloud service account JSON. The service account email must have Editor access to the Google Sheet. Sheet ID: `11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA`

---

## Data Schema

**Primary CSV:** `C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv`
**Backup CSV:** `C:\Users\user\Downloads\leads.csv` (scraper writes to both simultaneously)

### CSV Columns (12 total — order matters)

| # | Column | Example | Notes |
|---|---|---|---|
| 0 | `Type` | `Post` or `Comment` | Always one of these two values |
| 1 | `Post_ID` | `1rbbsls` | Reddit post ID (short alphanumeric). Comments share their parent post's ID. |
| 2 | `Author` | `bobo_the_hobo_dog` | Reddit username |
| 3 | `Phone` | `N/A` | Always `N/A` — placeholder for future CRM use |
| 4 | `Subreddit` | `Mortgages` | Sub name without r/ prefix |
| 5 | `Title` | `7% → 5.875% worth it?` | Post title (same for all comments under a post) |
| 6 | `Body` | `Hey all, I know...` | Full post body or comment text |
| 7 | `Link` | `https://reddit.com/r/...` | Permalink to post. Comments share the parent post URL. |
| 8 | `Post Time (UTC)` | `2026-02-22 04:02:02 UTC` | When the Reddit post was originally created |
| 9 | `Comment Count` | `4` | Number of comments on the post at time of capture |
| 10 | `Caught Time (UTC)` | `2026-02-22 04:16:52 UTC` | When the scraper first captured this row |
| 11 | `Client` | *(empty)* | Reserved for CRM tagging — not populated by scraper |

**Row ordering:** Posts and their Comments are grouped together in the CSV — a Post row is always immediately followed by its Comment rows before the next Post begins.

---

## Subreddits Monitored (20)

```
Mortgages, FirstTimeHomeBuyer, refinance, personalfinance,
RealEstate, RealEstateInvesting, Homeowners, FirstTimeHomeSeller,
povertyfinance, DebtFree, credit, loanoriginators, investing,
homebuying, REBubble, financialindependence, fatFIRE, Frugal,
ChubbyFIRE, leanfire
```

**Best performing subs (by post volume):**
- r/Mortgages — highest quality, mortgage-specific
- r/personalfinance — high volume, some noise
- r/credit — high volume, noisy (many credit card posts)
- r/refinance — very targeted
- r/REBubble — mostly relevant

---

## Keywords Used for Title Matching (39)

```
mortgage, rate, refi, lender, credit, buy home, first time, pre-approve,
interest rate, 7%, 7.5%, 8%, high rate, fha, va loan, conventional,
pmi, down payment, closing cost, pre-qual, underwater, cash out,
heloc, home equity, arm loan, adjustable, rate lock, buydown,
can't afford, cant afford, too high, trapped, stuck at, payment,
home loan, loan officer, broker, points, origination, qualify,
debt to income, dti, escrow, appraisal, refinancing
```

**Noise warning:** `credit`, `rate`, and `payment` are very broad — they match many non-mortgage posts in r/credit, r/personalfinance, and r/investing. The cleanest signals are: `mortgage`, `refi`, `refinancing`, `pmi`, `heloc`, `va loan`, `fha`, `down payment`.

**Keyword → Subreddit performance breakdown (from ~300 posts):**

| Keyword | Total | Top Subs |
|---|---|---|
| credit | 95 | credit(42), personalfinance(27), DebtFree(11) |
| rate | 77 | Mortgages(18), personalfinance(9), REBubble(9) |
| refi | 74 | refinance(33), Mortgages(26) |
| mortgage | 64 | Mortgages(23), REBubble(11), refinance(9) |
| payment | 29 | personalfinance(6), FirstTimeHomeBuyer(4), Mortgages(4) |
| lender | 24 | Mortgages(5), loanoriginators(5), refinance(4) |
| first time | 20 | Mortgages(4), homebuying(3), personalfinance(3) |

---

## Scraper Behavior

- Shuffles subreddit order each cycle to vary access patterns
- Fetches 50 most recent posts per subreddit (`/new.json?limit=50`)
- Checks each post title against all keywords (case-insensitive, substring match)
- If matched and not in `seen_ids`, fetches full post + all comments via the post's `.json` endpoint
- Writes one Post row + N Comment rows to CSV immediately, flushes to disk
- Also appends to Google Sheets if connection is available
- Sleeps **10–15 seconds** between each subreddit
- Sleeps **600–900 seconds (10–15 minutes)** between full cycles
- Rate limit protection: uses rotating mobile User-Agent strings to avoid 429s

---

## Dashboard (`dashboard.py`)

- Flask web server on **http://localhost:5000**
- Auto-refreshes every **5 seconds** via JavaScript polling `/api/data`
- Reads `leads.csv` fresh on every API call (no caching)
- Returns the **last 100 rows** of the CSV in the JSON response
- Shows stats: total Posts, total Comments, last updated timestamp
- Clickable links to original Reddit posts
- Expandable rows for long body text

**Key config in dashboard.py:**
```python
CSV_PATH = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv"
SHEET_ID = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
```

---

## Google Sheets

**Sheet URL:** https://docs.google.com/spreadsheets/d/11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA

The scraper writes to Google Sheets live as it finds posts (via `worksheet.append_rows()`). The sheet also has row grouping — comment rows are grouped/collapsed under their parent post row for readability.

To do a full sync from local CSV → Google Sheets (e.g., after a reset):
```bash
python sync_csv_to_sheets.py
```

---

## Utility Scripts

These were created during debugging sessions and are kept for reference:

| Script | Purpose |
|---|---|
| `sync_csv_to_sheets.py` | Push entire local CSV to Google Sheets (clears sheet first) |
| `clean_csv.py` | Fix/normalize CSV column alignment issues |
| `check_csv.py` | Inspect CSV structure and row counts |
| `check_links.py` | Validate URLs in the CSV |
| `inspect_sheet.py` | Read and inspect Google Sheet contents |
| `inspect_api.py` | Debug Google Sheets API responses |
| `reset_sheet.py` | Clear the Google Sheet |
| `revert_sheet.py` | Restore sheet to a previous state |
| `clear_sheet.py` | Wipe all rows from Google Sheet |
| `update_sheets_postid.py` | Retrofit post IDs into older sheet rows |
| `verify_sheet.py` | Compare sheet vs CSV for consistency |
| `sync_to_sheet.py` | Earlier version of the sync utility |
| `debug_sheet.py` | One-off debug for sheet API issues |

---

## Known Issues & Historical Fixes

### 1. CSV Field Misalignment (February 2026)
**Symptom:** Dashboard shows scrambled data — author names in the Type field, URLs in the Title field, etc.
**Cause:** The scraper went through multiple format iterations. Older rows in the CSV were written without `Type` and `Post_ID` columns, causing an 8 or 9-column row instead of 12. When the header stayed at 12 columns, the data appeared to shift.
**Fix:** `clean_csv.py` detects row length and reconstructs missing columns by:
- 8-col rows: prepend `Post` + extract Post_ID from URL
- 9-col Post rows: insert Post_ID extracted from URL at position 1
- 9-col Comment rows: same — extract parent Post_ID from URL
- 10-col rows: insert Post_ID, keep comment count
- 11-col Comment rows: move Caught Time from wrong column slot
**Recovery script used:** inline Python (see session history). Always back up CSV before running repairs.

### 2. Dashboard Not Updating
**Symptom:** Dashboard shows stale data / wrong post count
**Cause A:** `CSV_PATH` in `dashboard.py` pointed to the stale Downloads copy instead of the active OneDrive path.
**Fix:** Verify `CSV_PATH = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv"` in dashboard.py.
**Cause B:** Old Flask process still running after code changes.
**Fix:** Kill all Python processes before restarting:
```powershell
Get-Process python* | Stop-Process -Force
```

### 3. Flask Not Found on Restart
**Symptom:** `ModuleNotFoundError: No module named 'flask'`
**Cause:** Dependencies not installed in the current Python environment.
**Fix:**
```bash
python -m pip install flask gspread requests beautifulsoup4 python-dotenv
```

### 4. Slow Post Collection Rate
**Symptom:** Only 3–6 posts per hour after a fresh start
**Cause:** This is expected behavior. The scraper scans ~950 posts per cycle but only ~0.3% match the keyword filter and aren't already seen. After a CSV reset, `seen_ids.json` still has old IDs — posts already scraped won't be re-captured.
**Normal rate:** ~3–10 new posts per hour depending on Reddit activity.
**To restore historical data after a reset:** Use the CSV backup repair script (see session history) which fixes column alignment and merges old + new data.

### 5. seen_ids Preventing Re-capture After Reset
**Symptom:** CSV was reset but scraper isn't finding posts it found before
**Cause:** `seen_ids.json` persists across restarts and marks old posts as already seen.
**Fix:** Do NOT delete seen_ids.json unless you want to re-capture everything from scratch. Instead, restore from the CSV backup using the repair/merge script.

### 6. Google Sheets Row Limit / Grouping
The scraper uses row grouping in Sheets to collapse comments under posts. On startup it runs `retrofit_groups()` (applies grouping to historical rows) and `collapse_existing_groups()` (collapses open groups). These run once per session and can take 2–5 minutes on first launch. The sheet is pre-expanded to 100,000 rows to prevent capacity errors.

---

## File Paths (hardcoded — Windows machine)

| Variable | Path |
|---|---|
| `CSV_PATH` (scraper + dashboard) | `C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv` |
| `CSV_LOCAL` (scraper backup) | `C:\Users\user\Downloads\leads.csv` |
| `SEEN_IDS_FILE` | `C:\Users\user\OneDrive\Desktop\Reddit Mortgage\seen_ids.json` |
| `POST_ROWS_FILE` | `C:\Users\user\OneDrive\Desktop\Reddit Mortgage\post_rows.json` |
| `SHEET_ID` | `11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA` |

---

## Quick Start Checklist (after pulling fresh)

1. `credentials.json` present in project folder ✓
2. `.env` present with Reddit API credentials ✓
3. Install deps: `python -m pip install flask gspread requests beautifulsoup4 python-dotenv` ✓
4. `leads.csv` — restore from backup or let scraper rebuild from scratch ✓
5. `seen_ids.json` — keep existing to avoid re-scraping, or delete to start fresh ✓
6. Start scraper: `python scraper.py > scraper.log 2>&1 &` ✓
7. Start dashboard: `python dashboard.py > dashboard.log 2>&1 &` ✓
8. Open http://localhost:5000 ✓
