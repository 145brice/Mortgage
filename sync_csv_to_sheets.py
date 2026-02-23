#!/usr/bin/env python3
"""
Sync all CSV data to Google Sheets with proper grouping and formatting.
"""

import csv
import gspread
import time

SHEET_ID = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
CSV_PATH = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv"

def sync_csv_to_sheets():
    print("Connecting to Google Sheets...")
    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.sheet1

    print("Reading CSV data...")
    rows = []
    with open(CSV_PATH, 'r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames

        # Write header first
        rows.append(list(header))

        # Read all data rows
        for row in reader:
            row_values = [row.get(col, '') for col in header]
            rows.append(row_values)

    print(f"Loaded {len(rows) - 1} data rows from CSV")

    # Clear the sheet
    print("Clearing existing Google Sheet...")
    ws.clear()

    # Write all rows in batches (Google Sheets has limits)
    print("Writing data to Google Sheets...")
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        print(f"  Writing rows {i} to {i + len(batch)}...")
        ws.append_rows(batch, value_input_option='RAW')
        time.sleep(1)  # Be nice to the API

    print("Formatting Google Sheet...")
    sheet_id = ws._properties['sheetId']

    # Auto-resize columns
    sh.batch_update({
        "requests": [{
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS"
                }
            }
        }]
    })

    # Freeze header row
    sh.batch_update({
        "requests": [{
            "updateSheetProperties": {
                "fields": "gridProperties.frozenRowCount",
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 1
                    }
                }
            }
        }]
    })

    # Format header row (bold, background color)
    sh.batch_update({
        "requests": [{
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {
                            "red": 0.2,
                            "green": 0.4,
                            "blue": 0.8
                        },
                        "textFormat": {
                            "bold": True,
                            "foregroundColor": {
                                "red": 1,
                                "green": 1,
                                "blue": 1
                            }
                        }
                    }
                },
                "fields": "userEnteredFormat"
            }
        }]
    })

    print(f"\nSync complete!")
    print(f"  Total rows in sheet: {len(rows)}")
    print(f"  Data rows: {len(rows) - 1}")
    print(f"  Posts + Comments synced to Google Sheets")

if __name__ == '__main__':
    try:
        sync_csv_to_sheets()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
