#!/usr/bin/env python3
"""Test script to verify what Flask is serving"""

import requests
import sys

try:
    response = requests.get('http://localhost:5000', timeout=5)
    html = response.text

    print("=" * 60)
    print("FLASK SERVER TEST RESULTS")
    print("=" * 60)

    checks = {
        'pagination-controls': 'pagination-controls' in html,
        'Posted column header': '<th>Posted</th>' in html,
        'Caught column header': '<th>Caught</th>' in html,
        'Rows per page dropdown': 'rows-per-page' in html,
        'Pagination buttons': 'prev-btn' in html and 'next-btn' in html,
    }

    for check, result in checks.items():
        status = "[YES]" if result else "[NO]"
        print(f"{status}: {check}")

    # Extract table headers
    import re
    headers = re.findall(r'<th[^>]*>([^<]*)<', html)
    print(f"\nTable headers found: {headers}")

    print(f"\nHTML response length: {len(html)} characters")

    if all(checks.values()):
        print("\n[YES] ALL FEATURES FOUND - Dashboard is correct!")
        sys.exit(0)
    else:
        print("\n[NO] SOME FEATURES MISSING - There may be an issue")
        sys.exit(1)

except requests.exceptions.ConnectionError:
    print("[NO] Cannot connect to http://localhost:5000")
    print("Make sure Flask is running!")
    sys.exit(1)
except Exception as e:
    print(f"[NO] Error: {e}")
    sys.exit(1)
