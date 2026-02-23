import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import json
import gspread
import re
import os
from dotenv import load_dotenv

load_dotenv()

USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Mobile Safari/537.36"
]

SUBS = [
    "Mortgages", "FirstTimeHomeBuyer", "refinance", "personalfinance",
    "RealEstate", "RealEstateInvesting", "Homeowners",
    "FirstTimeHomeSeller", "povertyfinance", "DebtFree", "credit",
    "loanoriginators", "investing", "homebuying", "REBubble",
    "financialindependence", "fatFIRE", "Frugal", "ChubbyFIRE", "leanfire"
]

KEYWORDS = [
    "mortgage", "rate", "refi", "lender", "credit", "buy home", "first time", "pre-approve",
    "interest rate", "7%", "7.5%", "8%", "high rate", "fha", "va loan", "conventional",
    "pmi", "down payment", "closing cost", "pre-qual", "underwater", "cash out",
    "heloc", "home equity", "arm loan", "adjustable", "rate lock", "buydown",
    "can't afford", "cant afford", "too high", "trapped", "stuck at", "payment",
    "home loan", "loan officer", "broker", "points", "origination", "qualify",
    "debt to income", "dti", "escrow", "appraisal", "refinancing"
]

CSV_PATH = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv"
CSV_LOCAL = r"C:\Users\user\Downloads\leads.csv"
SEEN_IDS_FILE = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\seen_ids.json"
POST_ROWS_FILE = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\post_rows.json"


def open_csv(path):
    exists = os.path.isfile(path)
    f = open(path, "a", newline='', encoding="utf-8")
    w = csv.writer(f)
    if not exists:
        w.writerow(["Type", "Post_ID", "Author", "Phone", "Subreddit", "Title", "Body", "Link", "Post Time (UTC)", "Comment Count", "Caught Time (UTC)", "Client"])
        f.flush()
    return f, w


def load_seen_ids():
    if os.path.isfile(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def save_seen_ids(seen):
    with open(SEEN_IDS_FILE, 'w') as f:
        json.dump(list(seen), f)


def load_post_rows():
    if os.path.isfile(POST_ROWS_FILE):
        with open(POST_ROWS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_post_rows(post_rows):
    with open(POST_ROWS_FILE, 'w') as f:
        json.dump(post_rows, f)


def apply_row_group(sh, worksheet, post_row_1indexed, num_comments):
    """Group comment rows under their post row and collapse them immediately.

    Google Sheets merges adjacent groups at the same depth, so after addDimensionGroup
    the actual group range may be larger than requested.  We fetch the real groups
    from the API and collapse any uncollapsed ones that cover our new rows.
    """
    if num_comments == 0:
        return
    try:
        sheet_id = worksheet._properties['sheetId']
        start_idx = post_row_1indexed      # 0-indexed first comment row
        end_idx = post_row_1indexed + num_comments

        # Step 1: add the group
        sh.batch_update({"requests": [{
            "addDimensionGroup": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start_idx,
                    "endIndex": end_idx
                }
            }
        }]})

        # Step 2: fetch actual group ranges (adjacent groups may have merged)
        resp = sh.client.request(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{sh.id}",
            params={"fields": "sheets(properties.sheetId,rowGroups)"}
        )
        sheets_data = resp.json().get("sheets", [])
        row_groups = []
        for s in sheets_data:
            if s.get("properties", {}).get("sheetId") == sheet_id:
                row_groups = s.get("rowGroups", [])
                break

        # Step 3: collapse any uncollapsed group that covers our new comment rows
        to_collapse = [
            g for g in row_groups
            if not g.get("collapsed")
            and g.get("range", {}).get("startIndex", -1) <= start_idx
            and g.get("range", {}).get("endIndex", 0) >= end_idx
        ]
        if to_collapse:
            sh.batch_update({"requests": [
                {
                    "updateDimensionGroup": {
                        "dimensionGroup": {
                            "range": g["range"],
                            "depth": g.get("depth", 1),
                            "collapsed": True
                        },
                        "fields": "collapsed"
                    }
                }
                for g in to_collapse
            ]})
    except Exception as e:
        print(f"  [group] Error: {e}", flush=True)


def retrofit_groups(sh, worksheet):
    """Retroactively apply row grouping to all existing Post→Comment sequences."""
    print("[retrofit] Reading all sheet rows...", flush=True)
    try:
        all_values = worksheet.get_all_values()
    except Exception as e:
        print(f"[retrofit] Error reading sheet: {e}", flush=True)
        return

    sheet_id = worksheet._properties['sheetId']
    requests_list = []

    i = 1  # index 0 is the header row; start scanning from index 1
    while i < len(all_values):
        row = all_values[i]
        if row and row[0] == 'Post':
            # Find the run of Comment rows that follow
            j = i + 1
            while j < len(all_values) and all_values[j] and all_values[j][0] == 'Comment':
                j += 1
            num_comments = j - i - 1
            if num_comments > 0:
                # all_values[i] → sheet row i+1 (1-indexed) → sheet index i (0-indexed)
                # Comments: all_values[i+1..j-1] → sheet indices i+1..j-1 (0-indexed)
                # addDimensionGroup: startIndex=i+1 (inclusive), endIndex=j (exclusive)
                requests_list.append({
                    "addDimensionGroup": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": i + 1,
                            "endIndex": j
                        }
                    }
                })
            i = j
        else:
            i += 1

    if not requests_list:
        print("[retrofit] No Post->Comment groups found to apply.", flush=True)
        return

    print(f"[retrofit] Applying {len(requests_list)} groups in batches...", flush=True)
    chunk_size = 500
    for c in range(0, len(requests_list), chunk_size):
        chunk = requests_list[c:c + chunk_size]
        try:
            sh.batch_update({"requests": chunk})
            print(f"[retrofit] Batch {c // chunk_size + 1}: {len(chunk)} groups applied.", flush=True)
            time.sleep(2)
        except Exception as e:
            print(f"[retrofit] Batch {c // chunk_size + 1} error: {e}", flush=True)
    print("[retrofit] Done.", flush=True)


def collapse_existing_groups(sh, worksheet):
    """Collapse all existing row groups by reading them directly from the Sheets API."""
    print("[collapse] Fetching row groups from Sheets API...", flush=True)
    try:
        sheet_id = worksheet._properties['sheetId']
        # Ask the Sheets API for this spreadsheet's row group metadata
        resp = sh.client.request(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{sh.id}",
            params={"fields": "sheets(properties.sheetId,rowGroups)"}
        )
        sheets_data = resp.json().get("sheets", [])
    except Exception as e:
        print(f"[collapse] Error fetching groups: {e}", flush=True)
        return

    row_groups = []
    for s in sheets_data:
        if s.get("properties", {}).get("sheetId") == sheet_id:
            row_groups = s.get("rowGroups", [])
            break

    if not row_groups:
        print("[collapse] No existing row groups found in sheet.", flush=True)
        return

    already_collapsed = sum(1 for g in row_groups if g.get("collapsed"))
    to_collapse = [g for g in row_groups if not g.get("collapsed")]
    print(f"[collapse] {len(row_groups)} groups total, {already_collapsed} already collapsed, {len(to_collapse)} to collapse.", flush=True)

    if not to_collapse:
        print("[collapse] Nothing to do.", flush=True)
        return

    requests_list = [
        {
            "updateDimensionGroup": {
                "dimensionGroup": {
                    "range": g["range"],
                    "depth": g.get("depth", 1),
                    "collapsed": True
                },
                "fields": "collapsed"
            }
        }
        for g in to_collapse
    ]

    chunk_size = 500
    for c in range(0, len(requests_list), chunk_size):
        chunk = requests_list[c:c + chunk_size]
        try:
            sh.batch_update({"requests": chunk})
            print(f"[collapse] Batch {c // chunk_size + 1}: {len(chunk)} groups collapsed.", flush=True)
            time.sleep(2)
        except Exception as e:
            print(f"[collapse] Batch {c // chunk_size + 1} error: {e}", flush=True)
    print("[collapse] Done.", flush=True)


def ensure_row_capacity(sh, worksheet, target_rows=100000):
    """Expand the sheet to at least target_rows rows if needed."""
    try:
        current_rows = worksheet._properties['gridProperties']['rowCount']
        if current_rows >= target_rows:
            print(f"[capacity] Sheet already has {current_rows} rows.", flush=True)
            return
        sheet_id = worksheet._properties['sheetId']
        sh.batch_update({"requests": [{
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"rowCount": target_rows}
                },
                "fields": "gridProperties.rowCount"
            }
        }]})
        print(f"[capacity] Expanded sheet from {current_rows} to {target_rows} rows.", flush=True)
    except Exception as e:
        print(f"[capacity] Error expanding rows: {e}", flush=True)


csv_file, csv_writer = open_csv(CSV_PATH)
csv_local_file, csv_local_writer = open_csv(CSV_LOCAL)

print("Scraping Reddit (sending to Google Sheet + local CSV)...", flush=True)

seen_ids = load_seen_ids()
print(f"Loaded {len(seen_ids)} previously seen post IDs.", flush=True)

retrofit_done = False
collapse_done = False
post_row_map = load_post_rows()
print(f"Loaded {len(post_row_map)} post row mappings.", flush=True)

while True:
    random.shuffle(SUBS)
    sh = None
    worksheet = None
    try:
        gc = gspread.service_account(filename='credentials.json')
        sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Google Sheets setup failed: {e}. Skipping.", flush=True)

    # Ensure sheet has enough rows
    if worksheet and sh:
        ensure_row_capacity(sh, worksheet)

    # Run retrofit once on first successful sheet connection
    if not retrofit_done and worksheet and sh:
        retrofit_groups(sh, worksheet)
        retrofit_done = True

    # Collapse any already-grouped rows that aren't collapsed yet
    if not collapse_done and worksheet and sh:
        collapse_existing_groups(sh, worksheet)
        collapse_done = True

    for sub in SUBS:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=50"

        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking r/{sub}...", flush=True)
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()

            for post in data['data']['children']:
                p = post['data']
                title_lower = p['title'].lower()
                if any(kw in title_lower for kw in KEYWORDS) and p['id'] not in seen_ids:
                    try:
                        r = requests.get(
                            f"https://www.reddit.com{p['permalink']}.json",
                            headers={"User-Agent": headers["User-Agent"]},
                            timeout=10
                        )
                        if r.status_code == 200:
                            full = r.json()
                            post_data = full[0]['data']['children'][0]['data']
                            author = post_data.get('author', '[deleted]')
                            title = post_data['title']
                            selftext = post_data.get('selftext', '')
                            permalink = f"https://www.reddit.com{p['permalink']}"
                            created_utc = post_data['created_utc']
                            seen_ids.add(p['id'])
                            save_seen_ids(seen_ids)
                            post_time = datetime.utcfromtimestamp(created_utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                            caught_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

                            all_rows = [["Post", p['id'], author, "N/A", sub, title, selftext, permalink, post_time, p.get('num_comments', 0), caught_time, ""]]

                            for r_ in all_rows:
                                csv_writer.writerow(r_)
                                csv_local_writer.writerow(r_)
                            csv_file.flush()
                            csv_local_file.flush()

                            if worksheet:
                                worksheet.append_rows(all_rows)

                            print(f"  *** POST: r/{sub} - {title[:50]}...", flush=True)
                    except Exception as e:
                        print(f"Error fetching r/{sub}: {e}", flush=True)
        except Exception as e:
            print(f"Error r/{sub}: {e}", flush=True)

        time.sleep(random.uniform(10, 15))

    time.sleep(random.uniform(600, 900))
