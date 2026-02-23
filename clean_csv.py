import csv
import re

INPUT = r"C:\Users\user\Downloads\leads.csv"
OUTPUT = r"C:\Users\user\Downloads\leads.csv.clean"

rows_read = 0
rows_written = 0

with open(INPUT, 'r', encoding='utf-8') as infile:
    with open(OUTPUT, 'w', newline='', encoding='utf-8') as outfile:
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        
        # Write header
        writer.writeheader()
        
        # Clean and write rows
        for row in reader:
            rows_read += 1
            # Replace newlines with spaces in multi-line fields
            for key in row:
                if row[key]:
                    row[key] = ' '.join(row[key].split())
            
            writer.writerow(row)
            rows_written += 1

print(f"Cleaned CSV: {rows_read} rows read, {rows_written} rows written", flush=True)

# Backup old and replace
import shutil
shutil.move(INPUT, INPUT + ".bak")
shutil.move(OUTPUT, INPUT)
print(f"Original backed up to {INPUT}.bak", flush=True)
