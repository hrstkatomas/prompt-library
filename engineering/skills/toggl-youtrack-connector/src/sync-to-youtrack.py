#!/usr/bin/env python3
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path


def resolve_secret(value: str) -> str:
    """Resolve op:// references via 1Password CLI; return plain values unchanged."""
    if not value or not value.startswith('op://'):
        return value
    result = subprocess.run(['op', 'read', value], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'1Password lookup failed for {value!r}: {result.stderr.strip()}')
    return result.stdout.strip()


YT_BASE = os.environ.get('YOUTRACK_BASE_URL', '').rstrip('/')
YT_TOKEN = resolve_secret(os.environ.get('YOUTRACK_TOKEN') or os.environ.get('YOUTRACK_LSDEVTOOLS_TOKEN', ''))
TOGGL_TOKEN = resolve_secret(os.environ.get('TOGGL_TOKEN', ''))
MAPPING_PATH = Path.home() / '.youtrack-toggl-mapping.json'

if not YT_BASE:
    print('YOUTRACK_BASE_URL not set', file=sys.stderr)
    sys.exit(1)
if not YT_TOKEN:
    print('YOUTRACK_TOKEN or YOUTRACK_LSDEVTOOLS_TOKEN not set (plain value or op:// reference)', file=sys.stderr)
    sys.exit(1)
if not TOGGL_TOKEN:
    print('TOGGL_TOKEN not set (plain value or op:// reference)', file=sys.stderr)
    sys.exit(1)

_toggl_auth = 'Basic ' + base64.b64encode(f'{TOGGL_TOKEN}:api_token'.encode()).decode()


def toggl_get(path, params=None):
    url = f'https://api.track.toggl.com/api/v9{path}'
    if params:
        url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': _toggl_auth,
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Toggl GET {path}: {e.code} {e.read().decode()}')


def yt_post(path, body):
    req = urllib.request.Request(
        f'{YT_BASE}/api{path}',
        data=json.dumps(body).encode(),
        headers={
            'Authorization': f'Bearer {YT_TOKEN}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'YouTrack POST {path}: {e.code} {e.read().decode()}')


def load_mapping():
    if not MAPPING_PATH.exists():
        raise RuntimeError(
            f'Mapping file not found at {MAPPING_PATH}.\nRun sync-to-toggl first to build the mapping.'
        )
    return json.loads(MAPPING_PATH.read_text())


def save_mapping(mapping):
    MAPPING_PATH.write_text(json.dumps(mapping, indent=2))


def parse_date_range():
    args = sys.argv[1:]

    def get_flag(flag):
        try:
            i = args.index(flag)
            return args[i + 1]
        except (ValueError, IndexError):
            return None

    today = date.today()
    since = get_flag('--since')
    if since:
        until = get_flag('--until') or today.isoformat()
        return f'{since}T00:00:00+00:00', f'{until}T23:59:59+00:00', since, until

    days_arg = get_flag('--days')
    days = int(days_arg) if days_arg else 7
    from_date = today - timedelta(days=days)
    from_str = from_date.isoformat()
    today_str = today.isoformat()
    return f'{from_str}T00:00:00+00:00', f'{today_str}T23:59:59+00:00', from_str, today_str


def ms_timestamp(iso_str):
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    return int(dt.timestamp() * 1000)


def main():
    mapping = load_mapping()
    start_date, end_date, display_start, display_end = parse_date_range()

    project_to_issue = {
        data['toggl_project_id']: issue_id
        for issue_id, data in mapping['issues'].items()
    }

    print(f'Fetching Toggl entries: {display_start} → {display_end}')
    entries = toggl_get('/me/time_entries', {'start_date': start_date, 'end_date': end_date})

    synced_set = set(mapping['synced_entries'])
    to_sync = [
        e for e in entries
        if e['duration'] > 0
        and e.get('project_id') is not None
        and e['project_id'] in project_to_issue
        and e['id'] not in synced_set
    ]

    print(f'  {len(entries)} total, {len(to_sync)} to sync')
    if not to_sync:
        print('Nothing to sync.')
        return

    synced = failed = 0

    for entry in to_sync:
        issue_id = project_to_issue[entry['project_id']]
        minutes = entry['duration'] // 60
        if minutes < 1:
            print(f'  [SKIP] #{entry["id"]}: < 1 minute')
            continue
        description = entry.get('description') or '(no description)'
        print(f'  [SYNC] {issue_id} +{minutes}m "{description[:45]}" ... ', end='', flush=True)
        try:
            yt_post(f'/issues/{issue_id}/timeTracking/workItems', {
                'date': ms_timestamp(entry['start']),
                'duration': {'minutes': minutes},
                'text': f'Toggl #{entry["id"]}: {description}',
            })
            mapping['synced_entries'].append(entry['id'])
            print('done')
            synced += 1
        except Exception as e:
            print(f'FAILED: {e}')
            failed += 1

    save_mapping(mapping)
    print(f'\nDone: {synced} synced, {failed} failed')
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
