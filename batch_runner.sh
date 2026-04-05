#!/usr/bin/env bash
# batch_runner.sh - Process a list of job URLs through the full pipeline.
# Reads from batch/pending_urls.txt (one URL per line).
# Processes 5 at a time in parallel.
# Results go to batch/batch_results.tsv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PENDING="$SCRIPT_DIR/batch/pending_urls.txt"
RESULTS="$SCRIPT_DIR/batch/batch_results.tsv"
VENV="$SCRIPT_DIR/venv/bin/python3"
PYTHON="${VENV:-python3}"

PARALLEL=5

if [ ! -f "$PENDING" ]; then
    echo "No pending_urls.txt found at $PENDING"
    exit 1
fi

# Init results file
if [ ! -f "$RESULTS" ]; then
    echo -e "timestamp\turl\tstatus\tjob_id\tgrade\tarchetype\terror" > "$RESULTS"
fi

# Filter out comments and blanks
URLS=()
while IFS= read -r line; do
    line="${line%%#*}"  # strip comments
    line="${line//[[:space:]]/}"  # trim whitespace
    [[ -n "$line" ]] && URLS+=("$line")
done < "$PENDING"

TOTAL="${#URLS[@]}"
if [ "$TOTAL" -eq 0 ]; then
    echo "No URLs to process in $PENDING"
    exit 0
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  JobAgent Batch Processor"
echo "  URLs to process: $TOTAL"
echo "  Parallel workers: $PARALLEL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

process_url() {
    local url="$1"
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "  Processing: $url"

    # Insert the job into the DB via a small Python inline script
    result=$($PYTHON -c "
import sys, json, sqlite3, re, requests
from datetime import datetime, timezone
from pathlib import Path

url = sys.argv[1]
db_path = Path('$SCRIPT_DIR/jobs.db')
conn = sqlite3.connect(str(db_path))

# Check if already in DB
row = conn.execute('SELECT id FROM jobs WHERE url=?', [url]).fetchone()
if row:
    print(json.dumps({'job_id': row[0], 'status': 'existing'}))
    conn.close()
    sys.exit(0)

# Try to fetch the page and extract title/description
try:
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers, timeout=15)
    title = 'Untitled'
    desc  = ''
    m = re.search(r'<title>([^<]+)</title>', r.text, re.IGNORECASE)
    if m: title = m.group(1).strip()
    # Strip HTML for description
    text = re.sub(r'<[^>]+>', ' ', r.text)
    text = re.sub(r'\s+', ' ', text).strip()
    desc = text[:500]
except Exception as e:
    print(json.dumps({'error': str(e), 'status': 'fetch_failed'}))
    conn.close()
    sys.exit(0)

now = datetime.now(timezone.utc).isoformat()
source = re.sub(r'https?://(?:www\.)?([^/]+).*', r'\1', url)
cur = conn.execute('''
    INSERT INTO jobs (title, url, published_date, source, feed_name, category, description, fetched_at)
    VALUES (?,?,?,?,?,?,?,?)
''', [title, url, now, source, 'batch_import', 'Engineering', desc, now])
job_id = cur.lastrowid
conn.commit()
conn.close()
print(json.dumps({'job_id': job_id, 'status': 'inserted', 'title': title}))
" "$url" 2>&1)

    job_id=$(echo "$result" | $PYTHON -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('job_id',''))" 2>/dev/null || echo "")
    status=$(echo "$result"  | $PYTHON -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('status',''))" 2>/dev/null || echo "error")
    err=$(echo "$result"     | $PYTHON -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('error',''))" 2>/dev/null || echo "")

    grade=""
    archetype=""

    # Evaluate if we got a job_id
    if [ -n "$job_id" ] && [ "$status" != "error" ]; then
        eval_result=$(curl -s -X POST "http://localhost:5000/api/evaluate/$job_id" 2>/dev/null || echo "{}")
        grade=$(echo "$eval_result"    | $PYTHON -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('grade',''))" 2>/dev/null || echo "")
        archetype=$(echo "$eval_result" | $PYTHON -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('archetype',''))" 2>/dev/null || echo "")
    fi

    echo -e "$ts\t$url\t$status\t$job_id\t$grade\t$archetype\t$err" >> "$RESULTS"
    echo "    → $status | grade:$grade | arch:$archetype"
}

export -f process_url
export PYTHON SCRIPT_DIR RESULTS

# Process in parallel batches of $PARALLEL
for ((i=0; i<TOTAL; i+=PARALLEL)); do
    batch=("${URLS[@]:$i:$PARALLEL}")
    pids=()
    for url in "${batch[@]}"; do
        process_url "$url" &
        pids+=($!)
    done
    for pid in "${pids[@]}"; do
        wait "$pid" || true
    done
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Batch complete. Results: $RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
