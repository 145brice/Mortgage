import requests
from bs4 import BeautifulSoup
import csv
import time
import random
from datetime import datetime
import json
import gspread

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
    "RealEstate", "HousingMarket", "RealEstateInvesting", "Homeowners",
    "FirstTimeHomeSeller", "povertyfinance", "DebtFree", "credit",
    "loanoriginators", "investing", "homebuying", "REBubble"
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


SHEET_URL = "https://script.google.com/macros/s/AKfycby1NfCuO5f-577pgCUY0b24__CVUNZ4fXwfHWvUxvfjCBAoMzYWAqnY-vfmtkacFWAz/exec"

CSV_PATH = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv"

import os
csv_exists = os.path.isfile(CSV_PATH)
csv_file = open(CSV_PATH, "a", newline='', encoding="utf-8")
csv_writer = csv.writer(csv_file)
if not csv_exists:
    csv_writer.writerow(["Author", "Phone", "Subreddit", "Title", "Body", "Link", "Post Time (UTC)", "Caught Time (UTC)"])
    csv_file.flush()

print("Scraping Reddit (sending to Google Sheet + local CSV)...", flush=True)

seen_ids = set()

while True:
    random.shuffle(SUBS)
    try:
        gc = gspread.service_account(filename='credentials.json')
        sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Google Sheets setup failed: {e}. Skipping.", flush=True)
        worksheet = None
    for sub in SUBS:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
        
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Checking r/{sub}...", flush=True)
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            for post in data['data']['children']:
                p = post['data']
                title_lower = p['title'].lower()
                if any(kw in title_lower for kw in KEYWORDS) and p['id'] not in seen_ids:
                    # Fetch full post
                    try:
                        r = requests.get(f"https://www.reddit.com{p['permalink']}.json", headers={"User-Agent": headers["User-Agent"]}, timeout=10)
                        if r.status_code == 200:
                            post_data = r.json()[0]['data']['children'][0]['data']
                            author = post_data.get('author', '[deleted]')
                            title = post_data['title']
                            selftext = post_data.get('selftext', '')
                            permalink = f"https://www.reddit.com{p['permalink']}"
                            created_utc = post_data['created_utc']
                            seen_ids.add(p['id'])
                            post_time = datetime.utcfromtimestamp(created_utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                            caught_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                            row = [author, "N/A", sub, title, selftext, permalink, post_time, caught_time]
                            csv_writer.writerow(row)
                            csv_file.flush()
                            if worksheet:
                                worksheet.append_row(row)
                            print(f"  *** LEAD: r/{sub} - {title[:50]}... Appended to sheet + CSV", flush=True)
                    except Exception as e:
                        print(f"Error fetching r/{sub}: {e}", flush=True)
        except Exception as e:
            print(f"Error r/{sub}: {e}", flush=True)

        time.sleep(random.uniform(2.5, 4.5))
    
    time.sleep(random.uniform(120, 300))