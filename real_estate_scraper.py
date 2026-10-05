"""Scrape real-estate discussions from the 50 largest U.S. city subreddits.

This scraper is deliberately independent from scraper.py: it has its own CSV,
seen-ID file, log-friendly output, and optional Google Sheet destination.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import re
import time
from typing import Iterable

import requests
from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "real_estate_leads.csv"
DEFAULT_SEEN_IDS = BASE_DIR / "real_estate_seen_ids.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1",
]


@dataclass(frozen=True)
class City:
    rank: int
    name: str
    state: str
    subreddit: str


# U.S. Census Bureau Vintage 2025 incorporated-place estimates, ranked by
# July 1, 2025 population. A city's principal local subreddit is used where
# its literal name is not the active community (for example, WashingtonDC).
TOP_50_CITIES = [
    City(1, "New York City", "NY", "nyc"),
    City(2, "Los Angeles", "CA", "LosAngeles"),
    City(3, "Chicago", "IL", "chicago"),
    City(4, "Houston", "TX", "houston"),
    City(5, "Phoenix", "AZ", "phoenix"),
    City(6, "Philadelphia", "PA", "philadelphia"),
    City(7, "San Antonio", "TX", "sanantonio"),
    City(8, "San Diego", "CA", "sandiego"),
    City(9, "Dallas", "TX", "Dallas"),
    City(10, "Fort Worth", "TX", "FortWorth"),
    City(11, "Jacksonville", "FL", "jacksonville"),
    City(12, "Austin", "TX", "Austin"),
    City(13, "San Jose", "CA", "SanJose"),
    City(14, "Charlotte", "NC", "Charlotte"),
    City(15, "Columbus", "OH", "Columbus"),
    City(16, "Indianapolis", "IN", "indianapolis"),
    City(17, "San Francisco", "CA", "sanfrancisco"),
    City(18, "Seattle", "WA", "Seattle"),
    City(19, "Denver", "CO", "Denver"),
    City(20, "Nashville", "TN", "nashville"),
    City(21, "Oklahoma City", "OK", "okc"),
    City(22, "Washington", "DC", "washingtondc"),
    City(23, "El Paso", "TX", "ElPaso"),
    City(24, "Las Vegas", "NV", "vegaslocals"),
    City(25, "Boston", "MA", "boston"),
    City(26, "Detroit", "MI", "Detroit"),
    City(27, "Louisville", "KY", "Louisville"),
    City(28, "Portland", "OR", "PortlandOR"),
    City(29, "Memphis", "TN", "memphis"),
    City(30, "Baltimore", "MD", "baltimore"),
    City(31, "Milwaukee", "WI", "milwaukee"),
    City(32, "Albuquerque", "NM", "Albuquerque"),
    City(33, "Fresno", "CA", "fresno"),
    City(34, "Tucson", "AZ", "Tucson"),
    City(35, "Sacramento", "CA", "Sacramento"),
    City(36, "Atlanta", "GA", "Atlanta"),
    City(37, "Kansas City", "MO", "kansascity"),
    City(38, "Mesa", "AZ", "mesaaz"),
    City(39, "Raleigh", "NC", "raleigh"),
    City(40, "Colorado Springs", "CO", "ColoradoSprings"),
    City(41, "Miami", "FL", "Miami"),
    City(42, "Omaha", "NE", "Omaha"),
    City(43, "Virginia Beach", "VA", "VirginiaBeach"),
    City(44, "Long Beach", "CA", "longbeach"),
    City(45, "Oakland", "CA", "oakland"),
    City(46, "Minneapolis", "MN", "Minneapolis"),
    City(47, "Bakersfield", "CA", "Bakersfield"),
    City(48, "Tulsa", "OK", "tulsa"),
    City(49, "Tampa", "FL", "tampa"),
    City(50, "Aurora", "CO", "AuroraCO"),
]

# Skip a lower-ranked city when a higher-ranked city in the top 50 represents
# the same Metropolitan Statistical Area (MSA):
# Fort Worth -> Dallas, Mesa -> Phoenix, Long Beach -> Los Angeles,
# Oakland -> San Francisco, and Aurora -> Denver.
SAME_METRO_DUPLICATE_RANKS = {10, 38, 44, 45, 50}
TARGET_CITIES = [
    city for city in TOP_50_CITIES if city.rank not in SAME_METRO_DUPLICATE_RANKS
]

# All mortgage terms from both sets in scraper.py, plus broad real-estate
# intent. Every term is active on every run; there is no hourly rotation.
REAL_ESTATE_TERMS = sorted({
    "mortgage", "rate", "refi", "refinance", "refinancing", "refinance rates",
    "lender", "private lender", "loan officer", "home loan", "loan estimate",
    "loan modification", "loan commitment", "mortgage commitment", "rate lock",
    "lock rate", "float down", "rate guarantee", "rate sheet", "rate shopping",
    "fixed rate", "adjustable rate", "interest rate", "rate increase", "high rate",
    "best rates", "lowest rate", "compare rates", "APR", "APY", "7%", "7.5%", "8%",
    "FHA", "FHA insured", "FHA streamline", "VA loan", "VA streamline", "USDA loan",
    "conventional", "conventional loan", "jumbo loan", "portfolio loan", "ARM loan",
    "ARM conversion", "adjustable", "balloon payment", "15-year mortgage",
    "30-year mortgage", "construction loan", "renovation loan", "bridge loan",
    "hard money", "seller financing", "prepayment penalty", "origination",
    "origination fee", "points", "annual percentage", "good faith estimate",
    "credit", "bad credit", "credit repair", "credit report", "credit bureau",
    "credit freeze", "FICO score", "bankruptcy", "debt consolidation",
    "debt to income", "DTI", "qualify", "pre-qual", "prequalify", "pre-approve",
    "preapproved", "lender requirements", "underwriting", "underwriting requirements",
    "document collection", "processing", "payment", "lower payment", "principal",
    "principal payment", "principal reduction", "PMI", "down payment",
    "down payment assistance", "closing", "closing cost", "closing costs",
    "closing disclosure", "clear to close", "wire transfer", "escrow", "escrow account",
    "appraisal", "appraisal fee", "appraisal waived", "appraisal contingency",
    "inspection", "inspection contingency", "contingency", "rate contingency",
    "title insurance", "title search", "earnest money", "walkthrough", "HOA", "HOA approval",
    "homeowners insurance", "property tax", "property value", "equity", "home equity",
    "equity building", "equity release", "negative equity", "underwater", "HELOC",
    "HELOC rates", "HEL vs HELOC", "cash out", "cash-out refi", "no-cash-out refi",
    "forbearance", "foreclosure", "short sale", "deed in lieu", "can't afford",
    "cant afford", "too high", "trapped", "stuck at", "save money",
    "real estate", "realtor", "real estate agent", "listing agent", "buyers agent",
    "buyer's agent", "seller's agent", "broker", "brokerage", "MLS", "listing",
    "listed", "open house", "showing", "offer", "multiple offers", "counteroffer",
    "buy home", "buy a home", "buy a house", "buying a home", "buying a house",
    "home buyer", "homebuyer", "first time", "first-time buyer", "first time homebuyer",
    "home purchase", "home buying", "house hunting", "new homeowner", "homeowner",
    "homeownership", "sell home", "sell my home", "sell a house", "selling my house",
    "home seller", "FSBO", "for sale by owner", "asking price", "sale price",
    "property", "investment property", "rental property", "rental", "renting",
    "tenant", "landlord", "lease", "security deposit", "rent increase", "eviction",
    "real estate investing", "real estate investor", "BRRRR", "house hack",
    "house hacking", "fix and flip", "fixer upper", "flip house", "cap rate",
    "cash flow", "cash-on-cash", "NOI", "1031 exchange", "REIT", "REO",
    "wholesale real estate", "commercial real estate", "multifamily", "duplex",
    "triplex", "fourplex", "condo", "townhome", "townhouse", "co-op", "HOA fee",
    "zoning", "rezoning", "permit", "property line", "survey", "easement",
    "deed", "lien", "property management", "property manager", "new construction",
    "builder", "developer", "development", "vacant land", "land purchase",
}, key=str.casefold)

CSV_FIELDS = [
    "Post_ID", "City_Rank", "City", "State", "Subreddit", "Author", "Title",
    "Body", "Matched_Terms", "Score", "Comment_Count", "Link",
    "Post_Time_UTC", "Caught_Time_UTC",
]


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term.casefold()).replace(r"\ ", r"\s+")
    left = r"(?<!\w)" if term[0].isalnum() else ""
    right = r"(?!\w)" if term[-1].isalnum() else ""
    return re.compile(left + escaped + right, re.IGNORECASE)


TERM_PATTERNS = [(term, _term_pattern(term)) for term in REAL_ESTATE_TERMS]


def matched_terms(title: str, body: str) -> list[str]:
    """Return all real-estate terms found in a post title or body."""
    text = f"{title}\n{body}"
    return [term for term, pattern in TERM_PATTERNS if pattern.search(text)]


def load_seen_ids(path: Path) -> set[str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return set(value) if isinstance(value, list) else set()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()


def save_seen_ids(path: Path, seen_ids: set[str]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(sorted(seen_ids)), encoding="utf-8")
    temp_path.replace(path)


def append_rows(path: Path, rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    materialized = list(rows)
    if not materialized:
        return materialized
    new_file = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerows(materialized)
        handle.flush()
    return materialized


def connect_sheet():
    """Connect only when a separate REAL_ESTATE_SHEET_ID is configured."""
    sheet_id = os.getenv("REAL_ESTATE_SHEET_ID", "").strip()
    if not sheet_id:
        return None
    try:
        import gspread

        credentials = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        return gspread.service_account(filename=credentials).open_by_key(sheet_id).sheet1
    except Exception as exc:
        print(f"[sheet] Connection failed: {exc}", flush=True)
        return None


def fetch_city(session: requests.Session, city: City, limit: int) -> list[dict[str, object]]:
    url = f"https://www.reddit.com/r/{city.subreddit}/new.json"
    response = session.get(url, params={"limit": limit, "raw_json": 1}, timeout=20)
    if response.status_code == 429:
        raise RuntimeError("Reddit rate limit (HTTP 429)")
    response.raise_for_status()
    children = response.json().get("data", {}).get("children", [])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rows = []
    for child in children:
        post = child.get("data", {})
        title = post.get("title", "")
        body = post.get("selftext", "")
        terms = matched_terms(title, body)
        if not terms:
            continue
        created = datetime.fromtimestamp(post.get("created_utc", 0), timezone.utc)
        rows.append({
            "Post_ID": post.get("id", ""),
            "City_Rank": city.rank,
            "City": city.name,
            "State": city.state,
            "Subreddit": city.subreddit,
            "Author": post.get("author", "[deleted]"),
            "Title": title,
            "Body": body,
            "Matched_Terms": " | ".join(terms),
            "Score": post.get("score", 0),
            "Comment_Count": post.get("num_comments", 0),
            "Link": f"https://www.reddit.com{post.get('permalink', '')}",
            "Post_Time_UTC": created.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "Caught_Time_UTC": now,
        })
    return rows


def run_cycle(
    session: requests.Session,
    csv_path: Path,
    seen_path: Path,
    limit: int,
    request_delay: tuple[float, float],
    worksheet=None,
) -> int:
    seen_ids = load_seen_ids(seen_path)
    cities = TARGET_CITIES.copy()
    random.shuffle(cities)
    added = 0
    for index, city in enumerate(cities, 1):
        print(
            f"[{index:02d}/{len(cities)}] r/{city.subreddit} "
            f"({city.name}, {city.state})",
            flush=True,
        )
        try:
            rows = fetch_city(session, city, limit)
            new_rows = [row for row in rows if row["Post_ID"] not in seen_ids]
            append_rows(csv_path, new_rows)
            if worksheet and new_rows:
                worksheet.append_rows(
                    [[row[field] for field in CSV_FIELDS] for row in new_rows],
                    value_input_option="RAW",
                )
            for row in new_rows:
                seen_ids.add(str(row["Post_ID"]))
                print(f"  + {row['Title'][:80]}", flush=True)
            if new_rows:
                save_seen_ids(seen_path, seen_ids)
            added += len(new_rows)
        except Exception as exc:
            print(f"  [error] {exc}", flush=True)
            if "429" in str(exc):
                time.sleep(120)
        if index < len(cities):
            time.sleep(random.uniform(*request_delay))
    print(f"Cycle complete: {added} new real-estate posts.", flush=True)
    return added


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one 50-city cycle and exit")
    parser.add_argument("--limit", type=int, default=50, choices=range(1, 101), metavar="1-100")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--seen-ids", type=Path, default=DEFAULT_SEEN_IDS)
    parser.add_argument("--min-delay", type=float, default=4.0)
    parser.add_argument("--max-delay", type=float, default=7.0)
    parser.add_argument("--cycle-minutes", type=float, default=15.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise SystemExit("Delay values must satisfy 0 <= min-delay <= max-delay")
    if args.cycle_minutes < 0:
        raise SystemExit("cycle-minutes cannot be negative")

    session = requests.Session()
    session.headers.update({
        "User-Agent": os.getenv("REDDIT_USER_AGENT", random.choice(USER_AGENTS)),
        "Accept": "application/json",
    })
    worksheet = connect_sheet()
    print(
        f"Real-estate scraper: {len(TARGET_CITIES)} unique metros from the top "
        f"50 cities, {len(REAL_ESTATE_TERMS)} terms, "
        f"output={args.csv}",
        flush=True,
    )
    while True:
        run_cycle(
            session,
            args.csv,
            args.seen_ids,
            args.limit,
            (args.min_delay, args.max_delay),
            worksheet,
        )
        if args.once:
            break
        time.sleep(args.cycle_minutes * 60)


if __name__ == "__main__":
    main()
