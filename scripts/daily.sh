#!/usr/bin/env bash
set -euo pipefail
BASE="http://localhost:8080"
TOKEN="radar-internal-42"
DATE=$(date -I)

echo "[1/2] Ingest BODACC…"
curl -s "$BASE/collector/bodacc/ingest?token=$TOKEN&limit=20" | python3 -m json.tool

echo "[2/2] Recompute scores $DATE…"
curl -s -X POST "$BASE/admin/score-daily?token=$TOKEN&date=$DATE" | python3 -m json.tool
