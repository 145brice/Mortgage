import gspread
import re
import time

# Connect to Google Sheets
gc = gspread.service_account(filename='credentials.json')
sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
sh = gc.open_by_key(sheet_id)
worksheet = sh.sheet1

print("Reading all sheet data...", flush=True)
all_values = worksheet.get_all_values()

print(f"Found {len(all_values)} rows", flush=True)

# Check if Post_ID column already exists
if len(all_values) > 0 and all_values[0][1] == "Post_ID":
    print("Post_ID column already exists at column B. Skipping insert.", flush=True)
    # Just update any missing Post_IDs
    sheet_id_obj = worksheet._properties['sheetId']
    requests = []

    for row_num in range(1, len(all_values)):  # Skip header
        row = all_values[row_num]
        if not row:
            continue

        # Link is at column 6 (index 6)
        if len(row) > 6:
            link = row[6]
            # Extract post ID from link like https://www.reddit.com/r/subreddit/comments/ABC123/title/
            match = re.search(r'/comments/([a-z0-9]+)/', link)
            if match:
                post_id = match.group(1)
                # Check if Post_ID column (column 1, index 1) is empty
                if len(row) > 1 and not row[1]:
                    # Add update request
                    requests.append({
                        "updateCells": {
                            "range": {
                                "sheetId": sheet_id_obj,
                                "startRowIndex": row_num,
                                "endRowIndex": row_num + 1,
                                "startColumnIndex": 1,
                                "endColumnIndex": 2
                            },
                            "rows": [{
                                "values": [{
                                    "userEnteredValue": {"stringValue": post_id}
                                }]
                            }],
                            "fields": "userEnteredValue"
                        }
                    })

    if requests:
        print(f"Updating {len(requests)} cells with Post_IDs...", flush=True)
        chunk_size = 500
        for c in range(0, len(requests), chunk_size):
            chunk = requests[c:c + chunk_size]
            try:
                sh.batch_update({"requests": chunk})
                print(f"  Batch {c // chunk_size + 1}: {len(chunk)} cells updated.", flush=True)
                time.sleep(1)
            except Exception as e:
                print(f"  Batch error: {e}", flush=True)
else:
    print("Inserting Post_ID column at position B...", flush=True)

    # Insert a column at position 1 (B)
    sheet_id_obj = worksheet._properties['sheetId']
    sh.batch_update({
        "requests": [{
            "insertDimension": {
                "range": {
                    "sheetId": sheet_id_obj,
                    "dimension": "COLUMNS",
                    "startIndex": 1,
                    "endIndex": 2
                }
            }
        }]
    })

    print("Column inserted. Filling Post_ID values...", flush=True)
    time.sleep(2)

    # Now read the sheet again to get updated data
    all_values = worksheet.get_all_values()

    # Build batch update requests
    requests = []

    # Update header
    requests.append({
        "updateCells": {
            "range": {
                "sheetId": sheet_id_obj,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 1,
                "endColumnIndex": 2
            },
            "rows": [{
                "values": [{
                    "userEnteredValue": {"stringValue": "Post_ID"}
                }]
            }],
            "fields": "userEnteredValue"
        }
    })

    # Extract and fill Post_IDs for all data rows
    for row_num in range(1, len(all_values)):
        row = all_values[row_num]
        if not row:
            continue

        # Link is now at column 7 (index 7) after insertion
        if len(row) > 7:
            link = row[7]
            # Extract post ID from link like https://www.reddit.com/r/subreddit/comments/ABC123/title/
            match = re.search(r'/comments/([a-z0-9]+)/', link)
            if match:
                post_id = match.group(1)
                requests.append({
                    "updateCells": {
                        "range": {
                            "sheetId": sheet_id_obj,
                            "startRowIndex": row_num,
                            "endRowIndex": row_num + 1,
                            "startColumnIndex": 1,
                            "endColumnIndex": 2
                        },
                        "rows": [{
                            "values": [{
                                "userEnteredValue": {"stringValue": post_id}
                            }]
                        }],
                        "fields": "userEnteredValue"
                    }
                })

    print(f"Applying {len(requests)} cell updates in batches...", flush=True)
    chunk_size = 500
    for c in range(0, len(requests), chunk_size):
        chunk = requests[c:c + chunk_size]
        try:
            sh.batch_update({"requests": chunk})
            print(f"  Batch {c // chunk_size + 1}: {len(chunk)} cells updated.", flush=True)
            time.sleep(1)
        except Exception as e:
            print(f"  Batch error: {e}", flush=True)

print("Done!", flush=True)
