"""Lead quality scoring shared by the scraper dashboard."""
import re

HOT_PHRASES = [
    ("closing soon", 3, "closing soon"), ("closing next week", 3, "closing soon"),
    ("under contract", 3, "under contract"), ("offer accepted", 3, "offer accepted"),
    ("clear to close", 3, "near closing"), ("need a lender", 3, "needs lender"),
    ("need lender", 3, "needs lender"), ("looking for a lender", 3, "looking for lender"),
    ("recommend a lender", 3, "wants lender recommendation"),
    ("where can i get a loan", 3, "needs loan"), ("advice needed", 2, "asks for advice"),
    ("need advice", 2, "asks for advice"), ("loan estimate", 2, "reviewing loan estimate"),
    ("rate check", 2, "rate check"), ("rate quote", 2, "rate quote"),
    ("pre-approved", 2, "pre-approved"), ("preapproval", 2, "preapproval"),
    ("pre-approval", 2, "pre-approval"), ("first time home buyer", 2, "first-time buyer"),
    ("buying a house", 2, "buying home"), ("trying to buy", 2, "trying to buy"),
    ("looking to buy", 2, "looking to buy"), ("planning to buy", 2, "planning to buy"),
    ("cash to close", 2, "cash to close"), ("low appraisal", 2, "appraisal problem"),
    ("appraisal came in low", 2, "appraisal problem"), ("loan denied", 2, "loan denied"),
    ("denied", 1, "denied/problem"), ("can't afford", 2, "affordability pain"),
    ("cant afford", 2, "affordability pain"),
]

NEED_PATTERNS = [
    (re.compile(r"\b(i|we)\s+(need|want|am looking for|are looking for|am trying to|are trying to|plan to|planning to|hope to|hoping to)\b"), 2, "states need/want"),
    (re.compile(r"\b(anyone|somebody|someone)\s+(recommend|know|suggest)\b"), 2, "asks for recommendation"),
    (re.compile(r"\bshould\s+(i|we)\b"), 1, "asks decision question"),
    (re.compile(r"\bwhere\s+(can|should)\s+(i|we)\b"), 2, "asks where to go"),
]

COLD_PHRASES = [
    ("i am a lender", 5, "lender/pro"), ("i'm a lender", 5, "lender/pro"),
    ("im a lender", 5, "lender/pro"), ("loan officer here", 5, "loan officer/pro"),
    ("i am a loan officer", 5, "loan officer/pro"), ("i'm a loan officer", 5, "loan officer/pro"),
    ("nmls", 4, "loan professional"), ("mortgage broker here", 5, "broker/pro"),
    ("i am a realtor", 5, "realtor/pro"), ("i'm a realtor", 5, "realtor/pro"),
    ("im a realtor", 5, "realtor/pro"), ("realtor here", 5, "realtor/pro"),
    ("i am an agent", 5, "agent/pro"), ("i'm an agent", 5, "agent/pro"),
    ("as a lender", 4, "professional advice"), ("as a realtor", 4, "professional advice"),
    ("as an agent", 4, "professional advice"), ("as a loan officer", 4, "professional advice"),
    ("my clients", 3, "talking as professional"), ("dm me", 3, "sales/contact ask"),
    ("pm me", 3, "sales/contact ask"), ("happy to help", 2, "helper language"),
    ("you should", 1, "helper/advice language"),
]


def score_lead(row):
    row_type = (row.get("Type") or "post").strip().lower()
    title = row.get("Title", "")
    body = row.get("Body", "")
    text = f"{title} {body} {row.get('Matched Keywords', '')}".lower()
    score = 5 if row_type == "post" else 4
    reasons = []
    for phrase, points, reason in HOT_PHRASES:
        if phrase in text:
            score += points
            reasons.append(reason)
    for pattern, points, reason in NEED_PATTERNS:
        if pattern.search(text):
            score += points
            reasons.append(reason)
    if "?" in f"{title} {body}" and any(word in text for word in ("loan", "lender", "mortgage", "rate", "buy", "house", "home")):
        score += 1
        reasons.append("asks mortgage/real estate question")
    for phrase, points, reason in COLD_PHRASES:
        if phrase in text:
            score -= points
            reasons.append(reason)
    if row_type == "comment" and any(phrase in text for phrase in ("you need", "you should", "your lender", "talk to", "ask your")):
        score -= 2
        reasons.append("likely helper comment")
    score = max(1, min(10, score))
    return score, "; ".join(dict.fromkeys(reasons[:4])) if reasons else "keyword match"
