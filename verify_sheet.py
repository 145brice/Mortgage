import gspread
import re

gc = gspread.service_account(filename='credentials.json')
sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
sh = gc.open_by_key(sheet_id)
worksheet = sh.sheet1

print("Reading sheet header...", flush=True)
all_values = worksheet.get_all_values()

header = all_values[0]
print(f"\nHeader ({len(header)} columns):", flush=True)
for i, col in enumerate(header):
    print(f"  Col {i}: {col}", flush=True)

# Find key columns
post_id_idx = None
link_idx = None
type_idx = None
author_idx = None

for i, col in enumerate(header):
    if col == "Post_ID":
        post_id_idx = i
    elif col == "Link":
        link_idx = i
    elif col == "Type":
        type_idx = i
    elif col == "Author":
        author_idx = i

print(f"\nKey columns found:", flush=True)
print(f"  Type: {type_idx}", flush=True)
print(f"  Post_ID: {post_id_idx}", flush=True)
print(f"  Author: {author_idx}", flush=True)
print(f"  Link: {link_idx}", flush=True)

# Sample some rows
print(f"\nSampling first 5 data rows:", flush=True)
for row_num in range(1, min(6, len(all_values))):
    row = all_values[row_num]
    if row:
        type_val = row[type_idx] if type_idx is not None and len(row) > type_idx else "?"
        post_id_val = row[post_id_idx] if post_id_idx is not None and len(row) > post_id_idx else "?"
        author_val = row[author_idx] if author_idx is not None and len(row) > author_idx else "?"
        link_val = row[link_idx] if link_idx is not None and len(row) > link_idx else "?"

        print(f"\n  Row {row_num}:", flush=True)
        print(f"    Type: {type_val}", flush=True)
        print(f"    Post_ID: {post_id_val}", flush=True)
        print(f"    Author: {author_val[:30]}", flush=True)
        print(f"    Link: {link_val[:80] if link_val else '(empty)'}", flush=True)

# Check regex matching
print(f"\n\nChecking Post_ID extraction from Links...", flush=True)
match_count = 0
no_match_count = 0
sample_no_match = []

for row_num in range(1, min(1000, len(all_values))):
    row = all_values[row_num]
    if link_idx is not None and len(row) > link_idx:
        link = row[link_idx]
        if link:
            match = re.search(r'/comments/([a-z0-9]+)/', link)
            if match:
                match_count += 1
            else:
                no_match_count += 1
                if len(sample_no_match) < 3:
                    sample_no_match.append(link)

print(f"  In first 1000 rows:", flush=True)
print(f"    Matches: {match_count}", flush=True)
print(f"    No matches: {no_match_count}", flush=True)

if sample_no_match:
    print(f"\n  Sample non-matching links:", flush=True)
    for link in sample_no_match:
        print(f"    {link[:100]}", flush=True)

print(f"\n✓ Sheet structure verified (read-only)", flush=True)
