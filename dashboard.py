from flask import Flask, render_template, render_template_string, jsonify, Response, request
import ast
import csv
import os
import subprocess
import sys
from datetime import datetime
import json
import threading
import time
import gspread
from collections import defaultdict
from zoneinfo import ZoneInfo
from scraper_runtime import (
    CONFIG_PATH, PID_PATH, STATUS_PATH, STOP_PATH, load_runtime_config,
    request_stop, save_runtime_config,
)
from lead_scoring import score_lead

app = Flask(__name__)

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leads.csv')
SHEET_ID = '11iSHWnP7FhtmZqJ0h5eMtrO1fEvEH7iF84NvI9hbAVA'

# Enable only if you want the script to automatically normalize/fix the header row in Sheets
# WARNING: setting this to True will write to the spreadsheet's first row.
AUTO_FIX_HEADERS = False

SCRAPER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scraper.py')
SCRAPER_STDOUT = os.path.join(os.path.dirname(SCRAPER_PATH), 'scraper-live.stdout.log')
SCRAPER_STDERR = os.path.join(os.path.dirname(SCRAPER_PATH), 'scraper-live.stderr.log')


def scraper_pid():
    try:
        with open(PID_PATH, 'r', encoding='utf-8') as handle:
            pid = int(handle.read().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError, SystemError):
        return None


def read_json_file(path, fallback):
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return fallback


def tail_file(path, lines=35):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            return ''.join(handle.readlines()[-lines:])
    except OSError:
        return ''


def load_scraper_configuration():
    """Read display-safe scraper settings without importing the long-running scraper."""
    defaults = {
        "SUBS": [], "CORE_KEYWORDS": [], "RATE_KEYWORDS": [],
        "KEYWORDS_SET_A": [], "KEYWORDS_SET_B": [],
    }
    try:
        with open(SCRAPER_PATH, 'r', encoding='utf-8') as source_file:
            tree = ast.parse(source_file.read(), filename=SCRAPER_PATH)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in defaults:
                    value = ast.literal_eval(node.value)
                    if isinstance(value, list):
                        defaults[target.id] = value
    except (OSError, SyntaxError, ValueError):
        pass

    return {
        "subreddits": defaults["SUBS"],
        "keyword_sets": {
            "Always active — original": defaults["CORE_KEYWORDS"],
            "Always active — rates": defaults["RATE_KEYWORDS"],
            "Set A": defaults["KEYWORDS_SET_A"],
            "Set B": defaults["KEYWORDS_SET_B"],
        },
        "timing": [
            {"label": "Posts per subreddit", "value": "50 newest"},
            {"label": "Request timeout", "value": "10 seconds"},
            {"label": "Between subreddits", "value": "20–30 seconds, randomized"},
            {"label": "Between full cycles", "value": "10–15 minutes, randomized"},
            {"label": "Rate-limit pause", "value": "120 seconds"},
            {"label": "Keyword rotation", "value": "Every hour (Central Time)"},
            {"label": "Dashboard refresh", "value": "Every 5 seconds"},
        ],
        "toggles": [
            {"label": "Scraper loop", "enabled": True, "detail": "Continuous"},
            {"label": "Keyword rotation", "enabled": True, "detail": "Set A on even hours; Set B on odd hours"},
            {"label": "Random subreddit order", "enabled": True, "detail": "Reshuffled each cycle"},
            {"label": "Post re-sighting counts", "enabled": True, "detail": "Tracked for known posts"},
            {"label": "Google Sheets sync", "enabled": True, "detail": "Used when credentials connect"},
            {"label": "Automatic header repair", "enabled": AUTO_FIX_HEADERS, "detail": "Read-only safety setting"},
            {"label": "Dashboard auto-refresh", "enabled": True, "detail": "5-second interval"},
            {"label": "Central Time display", "enabled": True, "detail": "UTC retained in tooltips"},
        ],
    }

def load_resightings():
    """Load post resighting counters."""
    resightings_file = r"C:\Users\user\OneDrive\Desktop\Reddit Mortgage\post_resightings.json"
    if os.path.exists(resightings_file):
        try:
            with open(resightings_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def load_sheet_data():
    """Load data from CSV file (scraper writes to CSV)."""
    return read_csv_data()

def read_csv_data():
    """Read CSV data directly and enrich with resighting counters"""
    if not os.path.exists(CSV_PATH):
        print(f"CSV not found at {CSV_PATH}", flush=True)
        return [], {"posts": 0, "comments": 0}

    rows = []
    stats = {"posts": 0, "comments": 0}
    daily_counts = defaultdict(lambda: {"posts": 0, "comments": 0, "total": 0})
    resightings = load_resightings()

    try:
        with open(CSV_PATH, 'r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            header = reader.fieldnames if reader.fieldnames else []

            for row in reader:
                if row:
                    row_dict = {col: (row.get(col) or '') for col in header}
                    lead_score, lead_reason = score_lead(row_dict)
                    row_dict['Lead Score'] = lead_score
                    row_dict['Lead Reason'] = lead_reason

                    # Add resighting count if this is a post
                    if row.get('Type') == 'Post':
                        post_id = row.get('Post_ID', '')
                        row_dict['Resightings'] = str(resightings.get(post_id, 0))
                    else:
                        row_dict['Resightings'] = ''

                    rows.append(row_dict)

                    if row.get('Type') == 'Post':
                        stats['posts'] += 1
                    elif row.get('Type') == 'Comment':
                        stats['comments'] += 1

                    post_time = row.get('Post Time (UTC)', '')
                    try:
                        posted_utc = datetime.strptime(
                            post_time.replace(' UTC', ''), '%Y-%m-%d %H:%M:%S'
                        ).replace(tzinfo=ZoneInfo('UTC'))
                        posted_date = posted_utc.astimezone(ZoneInfo('America/Chicago')).date().isoformat()
                        daily_counts[posted_date]['total'] += 1
                        if row.get('Type') == 'Post':
                            daily_counts[posted_date]['posts'] += 1
                        elif row.get('Type') == 'Comment':
                            daily_counts[posted_date]['comments'] += 1
                    except (ValueError, TypeError):
                        pass

        stats['by_caught_date'] = [
            {"date": date, **counts}
            for date, counts in sorted(daily_counts.items(), reverse=True)
        ]

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

        <div class="pagination-controls" style="margin-bottom: 20px; background: white; padding: 15px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <label for="rows-per-page" style="margin-right: 10px; font-weight: 600;">Rows per page:</label>
                <select id="rows-per-page" style="padding: 8px 12px; border: 1px solid #ddd; border-radius: 5px; font-size: 0.9em;">
                    <option value="25">25</option>
                    <option value="50" selected>50</option>
                    <option value="100">100</option>
                    <option value="200">200</option>
                    <option value="999999">All</option>
                </select>
            </div>
            <div>
                <button id="prev-btn" style="padding: 8px 15px; margin-right: 10px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: 600;">← Previous</button>
                <span id="page-info" style="margin-right: 10px; font-weight: 600;">Page 1</span>
                <button id="next-btn" style="padding: 8px 15px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: 600;">Next →</button>
            </div>
        </div>

        <div class="data-table">
            <table>
                <thead>
                    <tr>
                        <th>Type</th>
                        <th>ID</th>
                        <th style="text-align: center;">Re-sights</th>
                        <th style="text-align: center;">Comments</th>
                        <th>Posted</th>
                        <th>Caught</th>
                        <th>Author</th>
                        <th>Content</th>
                        <th style="text-align: center;">Link</th>
                        <th>Sub</th>
                    </tr>
                </thead>
                <tbody id="data-body">
                    <tr><td colspan="10" class="no-data">Loading data...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // Convert UTC time string to Central Standard Time
        function convertUTCtoCST(utcTimeStr) {
            try {
                // Parse "2026-02-22 04:02:02 UTC" format
                const cleanStr = utcTimeStr.replace(' UTC', '').trim();
                const utcDate = new Date(cleanStr + ' UTC');
                const cstTime = utcDate.toLocaleString('en-US', {
                    timeZone: 'America/Chicago',
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false
                });
                // Return in format YYYY-MM-DD HH:MM
                return cstTime.replace(/(\d{2})\/(\d{2})\/(\d{4}), (\d{2}):(\d{2})/, '$3-$1-$2 $4:$5');
            } catch(e) {
                return utcTimeStr;
            }
        }

        let currentData = [];
        let sortColumn = null;
        let sortAsc = true;
        let currentPage = 1;
        let rowsPerPage = 50;

        function getPaginatedRows(rows) {
            const start = (currentPage - 1) * rowsPerPage;
            const end = start + rowsPerPage;
            return rows.slice(start, end);
        }

        function updatePaginationInfo(totalRows) {
            const maxPage = Math.ceil(totalRows / rowsPerPage);
            document.getElementById('page-info').textContent = `Page ${currentPage} of ${maxPage}`;
            document.getElementById('prev-btn').disabled = currentPage === 1;
            document.getElementById('next-btn').disabled = currentPage >= maxPage;
        }

        function renderTable(rows) {
            const tbody = document.getElementById('data-body');
            tbody.innerHTML = '';

            if (rows.length === 0) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = 10;
                td.className = 'no-data';
                td.textContent = 'No data yet. Scraper running...';
                tr.appendChild(td);
                tbody.appendChild(tr);
                return;
            }

            // Get paginated rows
            const paginatedRows = getPaginatedRows(rows);
            updatePaginationInfo(rows.length);

            paginatedRows.forEach(row => {
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

                // Re-sightings (engagement count)
                const resightCell = document.createElement('td');
                resightCell.style.textAlign = 'center';
                resightCell.style.fontWeight = 'bold';
                resightCell.style.color = row.Resightings && parseInt(row.Resightings) > 0 ? '#ff6b6b' : '#999';
                resightCell.textContent = row.Resightings || '-';
                tr.appendChild(resightCell);

                // Comment Count
                const commentCell = document.createElement('td');
                commentCell.style.textAlign = 'center';
                commentCell.style.fontWeight = 'bold';
                commentCell.style.color = '#667eea';
                commentCell.textContent = (row.Type === 'Post') ? (row['Comment Count'] || '0') : '-';
                tr.appendChild(commentCell);

                // Posted Time (UTC -> CST)
                const postedCell = document.createElement('td');
                postedCell.style.fontSize = '0.75em';
                postedCell.style.color = '#666';
                const postedTime = row['Post Time (UTC)'] || '';
                const postedCST = postedTime ? convertUTCtoCST(postedTime) : '-';
                postedCell.title = postedTime + ' (UTC)';
                postedCell.textContent = postedCST;
                tr.appendChild(postedCell);

                // Caught Time (UTC -> CST)
                const caughtCell = document.createElement('td');
                caughtCell.style.fontSize = '0.75em';
                caughtCell.style.color = '#666';
                const caughtTime = row['Caught Time (UTC)'] || '';
                const caughtCST = caughtTime ? convertUTCtoCST(caughtTime) : '-';
                caughtCell.title = caughtTime + ' (UTC)';
                caughtCell.textContent = caughtCST;
                tr.appendChild(caughtCell);

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
                    const cstTime = new Date().toLocaleTimeString('en-US', { timeZone: 'America/Chicago' });
                    document.getElementById('last-update').textContent = 'Last update: ' + cstTime + ' (CST)';

                    currentData = data.rows;
                    renderTable(currentData);
                })
                .catch(e => console.error('Error:', e));
        }

        // Add click handlers to headers
        document.querySelectorAll('thead th').forEach((th, idx) => {
            th.addEventListener('click', () => {
                const colMap = ['Type', 'Post_ID', 'Resightings', 'Comment Count', 'Post Time (UTC)', 'Caught Time (UTC)', 'Author', 'Title', 'Link', 'Subreddit'];
                if (idx < colMap.length) {
                    sortTable(colMap[idx]);
                }
            });
        });

        // Pagination controls
        document.getElementById('rows-per-page').addEventListener('change', (e) => {
            rowsPerPage = parseInt(e.target.value);
            currentPage = 1;
            renderTable(currentData);
        });

        document.getElementById('prev-btn').addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                renderTable(currentData);
            }
        });

        document.getElementById('next-btn').addEventListener('click', () => {
            const maxPage = Math.ceil(currentData.length / rowsPerPage);
            if (currentPage < maxPage) {
                currentPage++;
                renderTable(currentData);
            }
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
    return render_template('dashboard.html')


@app.route('/api/config')
def get_config():
    return jsonify(load_scraper_configuration())


@app.route('/admin')
def admin():
    return render_template('admin.html')


@app.route('/api/admin/status')
def admin_status():
    pid = scraper_pid()
    status = read_json_file(STATUS_PATH, {})
    status.update({
        'running': pid is not None,
        'pid': pid,
        'config': load_runtime_config(),
        'log': tail_file(SCRAPER_STDOUT),
        'errors_log': tail_file(SCRAPER_STDERR, 12),
    })
    if pid is None and status.get('state') not in ('stopped', 'blocked', None):
        status['state'] = 'stopped'
    return jsonify(status)


@app.route('/api/admin/config', methods=['POST'])
def admin_config():
    return jsonify({'ok': True, 'config': save_runtime_config(request.get_json(silent=True) or {})})


@app.route('/api/admin/run', methods=['POST'])
def admin_run():
    existing = scraper_pid()
    if existing:
        return jsonify({'ok': True, 'message': 'Scraper is already running.', 'pid': existing})
    try:
        os.remove(STOP_PATH)
    except FileNotFoundError:
        pass
    stdout = open(SCRAPER_STDOUT, 'w', encoding='utf-8')
    stderr = open(SCRAPER_STDERR, 'w', encoding='utf-8')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    process = subprocess.Popen(
        [sys.executable, '-u', SCRAPER_PATH], cwd=os.path.dirname(SCRAPER_PATH),
        stdout=stdout, stderr=stderr, creationflags=flags,
    )
    stdout.close()
    stderr.close()
    with open(PID_PATH, 'w', encoding='utf-8') as handle:
        handle.write(str(process.pid))
    return jsonify({'ok': True, 'message': 'Scraper started.', 'pid': process.pid})


@app.route('/api/admin/stop', methods=['POST'])
def admin_stop():
    pid = scraper_pid()
    if not pid:
        return jsonify({'ok': True, 'message': 'Scraper is already stopped.'})
    request_stop()
    return jsonify({'ok': True, 'message': 'Graceful stop requested. The current request will finish first.', 'pid': pid})


@app.route('/api/admin/kill', methods=['POST'])
def admin_kill():
    pid = scraper_pid()
    if not pid:
        return jsonify({'ok': True, 'message': 'Scraper is already stopped.'})
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, check=False)
    else:
        os.kill(pid, 9)
    try:
        os.remove(PID_PATH)
    except FileNotFoundError:
        pass
    return jsonify({'ok': True, 'message': 'Scraper stopped immediately.', 'pid': pid})

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

def sort_rows_by_post_time(rows):
    """Group posts with their comments, sort by Post Time (UTC) descending (newest first)."""
    if not rows:
        return []

    # Group posts with their comments
    groups = []
    current_group = []

    for row in rows:
        if row.get('Type') == 'Post':
            if current_group:
                groups.append(current_group)
            current_group = [row]
        else:
            current_group.append(row)

    if current_group:
        groups.append(current_group)

    # Sort groups by post's Post Time (UTC) descending - newest first
    def get_post_time(group):
        post = group[0]
        post_time = post.get('Post Time (UTC)', '')
        try:
            # Parse "2026-02-22 04:02:02 UTC" format
            from datetime import datetime
            dt = datetime.strptime(post_time.replace(' UTC', ''), '%Y-%m-%d %H:%M:%S')
            return dt.timestamp()
        except:
            return 0

    groups.sort(key=get_post_time, reverse=True)

    # Flatten back to list
    sorted_rows = []
    for group in groups:
        sorted_rows.extend(group)

    return sorted_rows

@app.route('/api/data')
def get_data():
    # Use Google Sheets (scraper uploads here, it was working!)
    rows, stats = load_sheet_data()

    # Sort rows by Post Time (UTC) descending - newest Reddit posts first
    sorted_rows = sort_rows_by_post_time(rows)

    # Return all sorted rows (or last 100 if preferred)
    data = {
        'rows': sorted_rows,
        'stats': stats,
        'scrape': read_json_file(STATUS_PATH, {}),
        'timestamp': datetime.now().isoformat()
    }

    return jsonify(data)

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5002
    print("Starting Reddit Mortgage Scraper Dashboard...", flush=True)
    print(f"Open your browser to: http://localhost:{port}", flush=True)
    app.run(debug=True, host='localhost', port=port, threaded=True)
