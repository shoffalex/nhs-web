#!/usr/bin/env bash
#
# Local development: the API on :8001 and the static site on :8000.
#
#   ./scripts/dev.sh
#   → site  http://127.0.0.1:8000
#   → API   http://127.0.0.1:8001/api/docs  (interactive OpenAPI docs)
#
# Two ports rather than one is deliberate: it matches how the site is served in
# production (nginx for files, uvicorn for /api only), so you never write code
# that accidentally depends on FastAPI serving the HTML. site/assets/js/api.js
# notices port 8000 and points itself at 8001.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT}/backend/.venv"

if [[ ! -d "${VENV}" ]]; then
  echo "==> Creating virtualenv"
  python3 -m venv "${VENV}"
  "${VENV}/bin/pip" install --quiet --upgrade pip
  "${VENV}/bin/pip" install --quiet -r "${ROOT}/backend/requirements-dev.txt"
fi

# Local dev secrets. Real deploys read /etc/nhs-web.env instead.
export NHS_DATABASE_URL="sqlite:///${ROOT}/backend/calendar.db"
export NHS_SECRET_KEY="${NHS_SECRET_KEY:-dev-secret-not-for-production}"
export NHS_ADMIN_PASSWORD="${NHS_ADMIN_PASSWORD:-dev}"

cleanup() {
  # Kill the whole process group so neither server is left orphaned on Ctrl-C.
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> API   http://127.0.0.1:8001/api/docs"
(cd "${ROOT}/backend" && "${VENV}/bin/uvicorn" app.main:app --reload --port 8001) &

echo "==> Site  http://127.0.0.1:8000    (admin password: ${NHS_ADMIN_PASSWORD})"
(cd "${ROOT}/site" && python3 -m http.server 8000) &

wait
