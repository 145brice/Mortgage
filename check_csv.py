import csv

csv_path = r"C:\Users\user\Downloads\leads.csv"

print("Checking local CSV format...", flush=True)
try:
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        print(f"\nHeader ({len(header)} columns):", flush=True)
        for i, col in enumerate(header):
            print(f"  Col {i}: {col}", flush=True)

        # Read last 3 rows
        rows = list(reader)
        print(f"\nTotal data rows: {len(rows)}", flush=True)

        if rows:
            print(f"\nLast 3 rows (format check):", flush=True)
            for row in rows[-3:]:
                print(f"  Type: {row[0] if len(row) > 0 else '?'}, Post_ID: {row[1] if len(row) > 1 else '?'}, Author: {row[2] if len(row) > 2 else '?'}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
