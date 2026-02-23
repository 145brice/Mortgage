from flask import Flask, render_template_string, jsonify, Response
import csv
import os
from datetime import datetime
import json
import threading
import time
import gspread

app = Flask(__name__)

CSV_PATH = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\leads.csv"
SHEET_ID = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'

# Enable only if you want the script to automatically normalize/fix the header row in Sheets
# WARNING: setting this to True will write to the spreadsheet's first row.
AUTO_FIX_HEADERS = False

def load_sheet_data():
    """Load data from CSV file (scraper writes to CSV)."""
    return read_csv_data()

def read_csv_data():
    """Read CSV data directly"""
    if not os.path.exists(CSV_PATH):
        print(f"CSV not found at {CSV_PATH}", flush=True)
        return [], {"posts": 0, "comments": 0}

    rows = []
    stats = {"posts": 0, "comments": 0}

    try:
        with open(CSV_PATH, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames if reader.fieldnames else []

            for row in reader:
                if row:
                    row_dict = {col: (row.get(col) or '') for col in header}
                    rows.append(row_dict)

                    if row.get('Type') == 'Post':
                        stats['posts'] += 1
                    elif row.get('Type') == 'Comment':
                        stats['comments'] += 1

        print(f"CSV: Loaded {len(rows)} rows, posts={stats['posts']}, comments={stats['comments']}", flush=True)

    except Exception as e:
        print(f"CSV Error: {e}", flush=True)

    return rows, stats

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Reddit Mortgage Scraper - Live Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            margin-bottom: 20px;
            text-align: center;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }
        .stat-card h3 {
            color: #667eea;
            font-size: 2em;
            margin-bottom: 5px;
        }
        .stat-card p {
            color: #666;
            font-size: 0.9em;
        }
        .last-update {
            color: white;
            text-align: center;
            margin-bottom: 15px;
            font-size: 0.9em;
        }
        .data-table {
            background: white;
            border-radius: 10px;
            overflow-x: auto;
            overflow-y: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        table {
            width: 100%;
            min-width: 900px;
            border-collapse: collapse;
        }
        thead {
            background: #667eea;
            color: white;
        }
        th {
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.95em;
            cursor: pointer;
            user-select: none;
        }
        th:hover {
            background: #5568d3;
        }
        th.sort-asc::after {
            content: ' ▲';
            font-size: 0.7em;
        }
        th.sort-desc::after {
            content: ' ▼';
            font-size: 0.7em;
        }
        td {
            padding: 8px 12px;
            border-bottom: 1px solid #eee;
            font-size: 0.85em;
            height: auto;
            line-height: 1.4;
            overflow: visible;
            white-space: normal;
            word-wrap: break-word;
        }
        tbody tr:hover {
            background: #f5f5f5;
        }
        tbody tr:nth-child(even) {
            background: #f9f9f9;
        }
        .type-post {
            background: #d4edda;
            color: #155724;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.85em;
        }
        .type-comment {
            background: #d1ecf1;
            color: #0c5460;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.85em;
        }
        a {
            color: #667eea;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .text-truncate {
            max-width: 350px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            display: inline-block;
        }
        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        .refresh-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #28a745;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Reddit Mortgage Scraper</h1>

        <div class="last-update">
            <span class="refresh-indicator"></span>
            <span id="last-update">Loading...</span>
            <span> | Auto-refreshing every 5 seconds</span>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3 id="post-count">0</h3>
                <p>Posts Found</p>
            </div>
            <div class="stat-card">
                <h3 id="comment-count">0</h3>
                <p>Comments Collected</p>
            </div>
            <div class="stat-card">
                <h3 id="total-count">0</h3>
                <p>Total Entries</p>
            </div>
        </div>

        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>ID</th>
                        <th>Author</th>
                        <th>Content</th>
                        <th style="text-align: center;">Link</th>
                        <th>Sub</th>
                    </tr>
                </thead>
                <tbody id="data-body">
                    <tr><td colspan="6" class="no-data">Loading data...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let currentData = [];
        let sortColumn = null;
        let sortAsc = true;

        function renderTable(rows) {
            const tbody = document.getElementById('data-body');
            tbody.innerHTML = '';

            if (rows.length === 0) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = 6;
                td.className = 'no-data';
                td.textContent = 'No data yet. Scraper running...';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            rows.forEach(row => {
                const tr = document.createElement('tr');

                // Type
                const typeCell = document.createElement('td');
                const typeSpan = document.createElement('span');
                typeSpan.className = row.Type === 'Post' ? 'type-post' : 'type-comment';
                typeSpan.textContent = row.Type === 'Post' ? 'POST' : 'COMMENT';
                typeCell.appendChild(typeSpan);
                tr.appendChild(typeCell);

                // ID
                const idCell = document.createElement('td');
                const idCode = document.createElement('code');
                idCode.style.fontSize = '0.7em';
                idCode.textContent = (row.Post_ID || '-').substring(0, 6);
                idCell.appendChild(idCode);
                tr.appendChild(idCell);

                // Author
                const authorCell = document.createElement('td');
                authorCell.style.fontSize = '0.8em';
                authorCell.style.maxWidth = '80px';
                authorCell.style.overflow = 'hidden';
                authorCell.textContent = (row.Author || '[deleted]').substring(0, 12);
                tr.appendChild(authorCell);

                // Content
                const text = row.Type === 'Post' ? (row.Title || '') : (row.Body || '');
                const textDisplay = text.substring(0, 35) + (text.length > 35 ? '...' : '');
                const contentCell = document.createElement('td');
                contentCell.style.maxWidth = '250px';
                contentCell.title = text;
                contentCell.textContent = textDisplay;
                tr.appendChild(contentCell);

                // Link (REAL CLICKABLE)
                const linkCell = document.createElement('td');
                linkCell.style.textAlign = 'center';
                const link = row.Link || '';
                if (link && link.trim()) {
                    const a = document.createElement('a');
                    a.href = link.trim();
                    a.target = '_blank';
                    a.rel = 'noopener noreferrer';
                    a.style.color = '#ff6b35';
                    a.style.textDecoration = 'none';
                    a.style.fontSize = '1.2em';
                    a.title = 'Click to open on Reddit';
                    a.innerHTML = '🔗 Link';
                    linkCell.appendChild(a);
                } else {
                    linkCell.textContent = '-';
                }
                tr.appendChild(linkCell);

                // Subreddit
                const subCell = document.createElement('td');
                subCell.style.fontSize = '0.8em';
                subCell.style.maxWidth = '100px';
                subCell.style.overflow = 'hidden';
                subCell.textContent = 'r/' + (row.Subreddit || '').substring(0, 10);
                tr.appendChild(subCell);

                tbody.appendChild(tr);
            });
        }

        function sortTable(column) {
            if (sortColumn === column) {
                sortAsc = !sortAsc;
            } else {
                sortColumn = column;
                sortAsc = true;
            }

            const sorted = [...currentData].sort((a, b) => {
                let aVal = a[column] || '';
                let bVal = b[column] || '';
                if (typeof aVal === 'string') aVal = aVal.toLowerCase();
                if (typeof bVal === 'string') bVal = bVal.toLowerCase();

                if (aVal < bVal) return sortAsc ? -1 : 1;
                if (aVal > bVal) return sortAsc ? 1 : -1;
                return 0;
            });

            // Update header indicators
            document.querySelectorAll('thead th').forEach(th => {
                th.classList.remove('sort-asc', 'sort-desc');
            });
            const headers = { 'Type': 0, 'ID': 1, 'Author': 2, 'Content (click 🔗 for link)': 3, 'Subreddit': 4 };
            const headerIdx = headers[column];
            if (headerIdx !== undefined) {
                document.querySelectorAll('thead th')[headerIdx].classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
            }

            renderTable(sorted);
        }

        function updateDashboard() {
            fetch('/api/data')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('post-count').textContent = data.stats.posts;
                    document.getElementById('comment-count').textContent = data.stats.comments;
                    document.getElementById('total-count').textContent = data.stats.posts + data.stats.comments;
                    document.getElementById('last-update').textContent = 'Last update: ' + new Date().toLocaleTimeString();

                    currentData = data.rows.reverse();
                    renderTable(currentData);
                })
                .catch(e => console.error('Error:', e));
        }

        // Add click handlers to headers
        document.querySelectorAll('thead th').forEach(th => {
            th.addEventListener('click', () => {
                const colNames = ['Type', 'Post_ID', 'Author', 'Title', 'Subreddit'];
                const colIdx = Array.from(th.parentNode.children).indexOf(th);
                const colMap = ['Type', 'Post_ID', 'Author', 'Title', 'Subreddit'];
                if (colIdx < colMap.length) {
                    sortTable(colMap[colIdx]);
                }
            });
        });

        // Initial load
        updateDashboard();

        // Refresh every 5 seconds
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/debug')
def debug():
    try:
        gc = gspread.service_account(filename='credentials.json')
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
        all_values = worksheet.get_all_values()

        return jsonify({
            "header": all_values[0] if all_values else [],
            "header_length": len(all_values[0]) if all_values else 0,
            "first_data_row": all_values[1] if len(all_values) > 1 else [],
            "first_data_row_length": len(all_values[1]) if len(all_values) > 1 else 0,
            "total_rows": len(all_values)
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/data')
def get_data():
    # Use Google Sheets (scraper uploads here, it was working!)
    rows, stats = load_sheet_data()

    # Return last 100 rows
    data = {
        'rows': rows[-100:] if rows else [],
        'stats': stats,
        'timestamp': datetime.now().isoformat()
    }

    return jsonify(data)

if __name__ == '__main__':
    print("Starting Reddit Mortgage Scraper Dashboard...", flush=True)
    print("Open your browser to: http://localhost:5000", flush=True)
    app.run(debug=False, host='localhost', port=5000, threaded=True)
