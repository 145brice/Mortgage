import gspread

gc = gspread.service_account(filename='credentials.json')
sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
sh = gc.open_by_key(sheet_id)
worksheet = sh.sheet1

all_values = worksheet.get_all_values()

print(f"Total rows: {len(all_values)}", flush=True)
print(f"\nFirst row (header): {all_values[0]}", flush=True)
print(f"\nFirst 5 data rows:", flush=True)
for i in range(1, min(6, len(all_values))):
    print(f"Row {i}: {all_values[i][:8]}", flush=True)
