"""Shared runtime state and controls for the scraper and local admin dashboard."""
import json
import os
import time
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'scraper_runtime.json')
STATUS_PATH = os.path.join(BASE_DIR, 'scraper_status.json')
PID_PATH = os.path.join(BASE_DIR, 'scraper.pid')
STOP_PATH = os.path.join(BASE_DIR, 'scraper.stop')

DEFAULT_CONFIG = {
    "continuous": True,
    "keyword_rotation": True,
    "randomize_subreddits": True,
    "track_resightings": True,
    "fetch_comments": True,
    "google_sheets": True,
    "posts_limit": 50,
    "subreddits_per_request": 5,
    "max_comments_per_post": 100,
    "comment_request_delay_sec": 12,
    "request_timeout_sec": 10,
    "subreddit_delay_min_sec": 2,
    "subreddit_delay_max_sec": 5,
    "cycle_delay_min_sec": 90,
    "cycle_delay_max_sec": 90,
    "rate_limit_pause_sec": 120,
}


def load_runtime_config():
    config = DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as handle:
            saved = json.load(handle)
        if isinstance(saved, dict):
            config.update({key: saved[key] for key in DEFAULT_CONFIG if key in saved})
    except (OSError, ValueError):
        pass
    return config


def save_runtime_config(values):
    config = load_runtime_config()
    for key, default in DEFAULT_CONFIG.items():
        if key not in values:
            continue
        if isinstance(default, bool):
            config[key] = bool(values[key])
        else:
            config[key] = max(0, int(values[key]))
    if config['subreddit_delay_max_sec'] < config['subreddit_delay_min_sec']:
        config['subreddit_delay_max_sec'] = config['subreddit_delay_min_sec']
    if config['cycle_delay_max_sec'] < config['cycle_delay_min_sec']:
        config['cycle_delay_max_sec'] = config['cycle_delay_min_sec']
    with open(CONFIG_PATH, 'w', encoding='utf-8') as handle:
        json.dump(config, handle, indent=2)
    return config


def update_status(**changes):
    status = {}
    try:
        with open(STATUS_PATH, 'r', encoding='utf-8') as handle:
            status = json.load(handle)
    except (OSError, ValueError):
        pass
    status.update(changes)
    status['updated_at'] = datetime.now(timezone.utc).isoformat()
    temporary = f"{STATUS_PATH}.{os.getpid()}.tmp"
    with open(temporary, 'w', encoding='utf-8') as handle:
        json.dump(status, handle, indent=2)
    for attempt in range(5):
        try:
            os.replace(temporary, STATUS_PATH)
            break
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


def stop_requested():
    return os.path.exists(STOP_PATH)


def clear_stop_request():
    try:
        os.remove(STOP_PATH)
    except FileNotFoundError:
        pass


def request_stop():
    with open(STOP_PATH, 'w', encoding='utf-8') as handle:
        handle.write('stop')


def interruptible_sleep(seconds):
    deadline = time.monotonic() + max(0, seconds)
    while time.monotonic() < deadline:
        if stop_requested():
            return False
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(1, remaining))
    return True
