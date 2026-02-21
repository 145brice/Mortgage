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
    "Mortgages", "FirstTimeHomeBuyer", "refinance", "credit", "personalfinance"
]

KEYWORDS = [
    "mortgage", "rate", "refi", "lender", "credit", "buy home", "first time", "pre-approve"
]

REQUIRED_KEYWORDS = [
    "help", "how do i", "what should i", "need lender", "bad credit", "7.5%", "refinance", "pre-qualify"
]

SHEET_URL = "https://script.google.com/macros/s/AKfycby1NfCuO5f-577pgCUY0b24__CVUNZ4fXwfHWvUxvfjCBAoMzYWAqnY-vfmtkacFWAz/exec"

print("Scraping Reddit (sending to Google Sheet)...")

while True:
    random.shuffle(SUBS)
    try:
        gc = gspread.service_account(filename='credentials.json')
        sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Google Sheets setup failed: {e}. Skipping.")
        worksheet = None
    for sub in SUBS:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=1"
        
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            for post in data['data']['children']:
                p = post['data']
                title_lower = p['title'].lower()
                if any(kw in title_lower for kw in KEYWORDS):
                    # Fetch full post
                    try:
                        r = requests.get(f"https://www.reddit.com{p['permalink']}.json", headers={"User-Agent": headers["User-Agent"]}, timeout=10)
                        if r.status_code == 200:
                            post_data = r.json()[0]['data']['children'][0]['data']
                            selftext = post_data.get('selftext', '').lower()
                            if any(req in selftext for req in REQUIRED_KEYWORDS):
                                # Save lead
                                author = post_data.get('author', '[deleted]')
                                title = post_data['title']
                                selftext = post_data.get('selftext', '')
                                permalink = f"https://www.reddit.com{p['permalink']}"
                                created_utc = post_data['created_utc']
                                if worksheet:
                                    worksheet.append_row([author, "N/A", sub, title, selftext, permalink, str(created_utc)])
                                    print(f"Lead: r/{sub} - {title[:50]}... Appended to sheet")
                    except Exception as e:
                        print(f"Error fetching r/{sub}: {e}")
        except Exception as e:
            print(f"Error r/{sub}: {e}")

        time.sleep(random.uniform(2.5, 4.5))
    
    time.sleep(random.uniform(120, 300))