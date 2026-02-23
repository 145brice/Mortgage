import gspread
import re

gc = gspread.service_account(filename='credentials.json')
sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
sh = gc.open_by_key(sheet_id)
worksheet = sh.sheet1

print("Reading all sheet data...", flush=True)
all_values = worksheet.get_all_values()

print(f"Total rows: {len(all_values)}", flush=True)
print(f"Header: {all_values[0]}", flush=True)

# Find the Link column
link_col_idx = None
for i, col_name in enumerate(all_values[0]):
    if col_name == "Link":
        link_col_idx = i
        break

print(f"\nLink column index: {link_col_idx}", flush=True)

if link_col_idx:
    sample_links = []
    matches = 0
    no_match = 0

    for row_num in range(1, min(100, len(all_values))):  # Check first 100 rows
        row = all_values[row_num]
        if len(row) > link_col_idx:
            link = row[link_col_idx]
            if link and link.startswith("http"):
                sample_links.append(link)
                match = re.search(r'/comments/([a-z0-9]+)/', link)
                if match:
                    matches += 1
                else:
                    no_match += 1
                    print(f"No match for: {link}", flush=True)

    print(f"\nMatches in first 100 rows: {matches}", flush=True)
    print(f"No matches in first 100 rows: {no_match}", flush=True)
    print(f"\nSample links:", flush=True)
    for link in sample_links[:5]:
        print(f"  {link}", flush=True)
