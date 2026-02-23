import gspread
import json

gc = gspread.service_account(filename='credentials.json')
sh = gc.open_by_key('11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA')
worksheet = sh.sheet1

all_values = worksheet.get_all_values()

print("=" * 80)
print("GOOGLE SHEETS INSPECTION")
print("=" * 80)
print(f"\nTotal rows: {len(all_values)}")
print(f"\nHeader (Row 0): {all_values[0]}")
print(f"Header length: {len(all_values[0])}")

# Filter to valid headers
valid_header = [h for h in all_values[0] if h.strip()]
print(f"\nValid header columns: {valid_header}")
print(f"Valid header length: {len(valid_header)}")

print(f"\n\nFirst 10 data rows (showing all columns):")
for i in range(1, min(11, len(all_values))):
    row = all_values[i]
    print(f"\nRow {i}: (length={len(row)})")
    print(f"  First 12 columns: {row[:12]}")

    # Now try the same mapping as the dashboard code
    row_dict = {}
    for j, col_name in enumerate(valid_header):
        if j < len(row):
            row_dict[col_name] = row[j]

    print(f"  Mapped dict Type={repr(row_dict.get('Type'))}, Post_ID={repr(row_dict.get('Post_ID'))}, Author={repr(row_dict.get('Author')[:20] if row_dict.get('Author') else None)}")

print("\n" + "=" * 80)
