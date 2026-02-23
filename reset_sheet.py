import gspread
import csv
import time

# Connect to Google Sheet
gc = gspread.service_account(filename='credentials.json')
sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
sh = gc.open_by_key(sheet_id)
worksheet = sh.sheet1

print("Clearing sheet...", flush=True)
worksheet.clear()
time.sleep(1)

print("Reading CSV data...", flush=True)
CSV_PATH = r"C:\Users\user\Downloads\leads.csv"

all_rows = []
with open(CSV_PATH, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        all_rows.append(row)

print(f"Loaded {len(all_rows)} rows from CSV (including header)", flush=True)

# Upload all rows in batches
batch_size = 500
for i in range(0, len(all_rows), batch_size):
    batch = all_rows[i:i + batch_size]
    try:
        worksheet.append_rows(batch)
        print(f"Uploaded rows {i}-{i + len(batch)}", flush=True)
        time.sleep(1)
    except Exception as e:
        print(f"Error uploading batch {i}: {e}", flush=True)

print("Sheet reset complete!", flush=True)
