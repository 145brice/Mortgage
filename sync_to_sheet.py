import gspread
import csv
import time

gc = gspread.service_account(filename='credentials.json')
sh = gc.open_by_key('11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA')
worksheet = sh.sheet1

print("Clearing Google Sheet...", flush=True)
worksheet.clear()
time.sleep(2)

print("Reading CSV...", flush=True)
with open(r"C:\Users\user\Downloads\leads.csv", 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    rows = list(reader)

print(f"Uploading {len(rows)} rows to Google Sheet...", flush=True)
worksheet.append_rows(rows, value_input_option='RAW')
print("Done!", flush=True)
