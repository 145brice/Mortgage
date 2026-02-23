import gspread

gc = gspread.service_account(filename='credentials.json')
sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
sh = gc.open_by_key(sheet_id)
worksheet = sh.sheet1

sheet_id_obj = worksheet._properties['sheetId']

print("Deleting the inserted column B (Post_ID)...", flush=True)

# Delete column B (index 1)
sh.batch_update({
    "requests": [{
        "deleteDimension": {
            "range": {
                "sheetId": sheet_id_obj,
                "dimension": "COLUMNS",
                "startIndex": 1,
                "endIndex": 2
            }
        }
    }]
})

print("Column deleted. Sheet reverted to original state.", flush=True)
