import gspread

gc = gspread.service_account(filename='credentials.json')
sheet_id = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'
sh = gc.open_by_key(sheet_id)
worksheet = sh.sheet1

print("Clearing corrupted data from Google Sheet...", flush=True)

# Clear all data
worksheet.clear()

# Write correct header
worksheet.append_rows([
    ["Type", "Post_ID", "Author", "Phone", "Subreddit", "Title", "Body", "Link", "Post Time (UTC)", "Comment Count", "Caught Time (UTC)", "Client"]
], value_input_option='RAW')

print("Sheet cleared and header added. Scraper will repopulate with fresh data.", flush=True)
