#!/usr/bin/env bash
#
# Deploy / update the NHS site on the server. Idempotent: safe to re-run, and
# the first run does the one-time setup (user, directories, venv, systemd unit,
# Caddy config).
#
# Run it on the droplet, as a user with sudo:
#
#   sudo bash /home/alex/GitHub/nhs-web/deploy/deploy.sh
#
# It never touches the database file beyond creating it, and it never writes
# /etc/nhs-web.env if one already exists — your secrets are left alone.

set -euo pipefail

REPO_DIR="/home/alex/GitHub/nhs-web"
REPO_OWNER="alex"
DATA_DIR="/var/lib/nhs-web"
ENV_FILE="/etc/nhs-web.env"
SERVICE_USER="nhs"
VENV="${REPO_DIR}/backend/.venv"

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run this with sudo." >&2
  exit 1
fi

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  echo "Expected a git checkout at ${REPO_DIR}." >&2
  echo "Clone it first:  git clone <repo-url> ${REPO_DIR}" >&2
  exit 1
fi

# ---------------------------------------------------------------- service user
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  say "Creating system user ${SERVICE_USER}"
  useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

# ------------------------------------------------------------------- data dir
say "Ensuring ${DATA_DIR} exists and is writable by ${SERVICE_USER}"
install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" -m 750 "${DATA_DIR}"

# -------------------------------------------------------------------- secrets
if [[ ! -f "${ENV_FILE}" ]]; then
  say "Creating ${ENV_FILE} with a generated secret key"
  # ADMIN_PASSWORD is deliberately left empty: the API refuses all writes until
  # you set it, so an unattended first deploy can't ship an open calendar.
  cat > "${ENV_FILE}" <<EOF
# Secrets for nhs-api. Root-owned, mode 600. Not in git.
NHS_DB_PATH=${DATA_DIR}/calendar.db
NHS_SECRET_KEY=$(openssl rand -hex 32)
NHS_ADMIN_PASSWORD=
NHS_TOKEN_TTL_HOURS=12
# No cross-origin requests in production — Caddy serves both on one origin.
NHS_CORS_ORIGINS=[]
EOF
  chmod 600 "${ENV_FILE}"
  echo "    Set NHS_ADMIN_PASSWORD in ${ENV_FILE}, then re-run this script."
else
  say "Keeping existing ${ENV_FILE}"
fi

# ----------------------------------------------------------------- code + deps
say "Updating code"
# As the checkout's owner, not root: keeps .git ownership clean and uses the
# owner's SSH key for private remotes.
sudo -u "${REPO_OWNER}" git -C "${REPO_DIR}" pull --ff-only

say "Installing Python dependencies"
if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install --quiet --upgrade pip
"${VENV}/bin/pip" install --quiet -r "${REPO_DIR}/backend/requirements.txt"

# Caddy serves files straight out of the checkout, and the nhs service user
# runs code from it, so both need to traverse in. o+x on the home directory
# grants traversal only — not listing or reading anything else in it.
chmod o+x "/home/${REPO_OWNER}"
chmod o+rx "${REPO_DIR}" "${REPO_DIR}/site"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${VENV}"

# ------------------------------------------------------------------- services
say "Installing systemd unit"
cp "${REPO_DIR}/deploy/systemd/nhs-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable nhs-api >/dev/null
systemctl restart nhs-api

say "Installing Caddy config"
cp "${REPO_DIR}/deploy/caddy/Caddyfile" /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy

# ---------------------------------------------------------------------- check
say "Health check"
sleep 1
if curl -fsS http://127.0.0.1:8000/api/health; then
  printf '\n\033[1;32m==>\033[0m Deploy complete.\n'
else
  printf '\n\033[1;31m==>\033[0m API did not answer. Check: journalctl -u nhs-api -n 50\n'
  exit 1
fi
