# Deploying pvnhs.com to the DigitalOcean droplet

Step-by-step plan for taking the site live on the `digitalocean` server
(68.183.109.62, Ubuntu 24.04), with Caddy serving `site/` and terminating TLS,
the FastAPI backend behind it, and SQLite storing the calendar. Everything runs
out of the existing checkout at `/home/alex/GitHub/nhs-web` — no second copy.

Server state when this plan was written (2026-08-10): repo pushed and present
at `/home/alex/GitHub/nhs-web`, Caddy not yet installed, ports 80/443/8000 all
free.

Decisions baked into this plan:

- **Caddy instead of nginx.** Caddy obtains and renews Let's Encrypt
  certificates automatically and redirects HTTP→HTTPS on its own — no certbot,
  no Cloudflare origin certificate, no manual TLS config. The trade: Cloudflare
  DNS records must be **DNS-only (grey cloud)**, because Caddy's ACME challenge
  needs to reach the droplet directly, not Cloudflare's proxy.
- **The server serves straight from `/home/alex/GitHub/nhs-web`.** `/home/alex`
  is mode `750`, so the `caddy` and `nhs` service users can't traverse into it
  until we run `chmod o+x /home/alex`. That grants traversal only (not
  listing/reading of anything else in the home directory) — `deploy.sh` does it
  as part of setup.
- **SQLite, no SQLAlchemy.** The backend is rewritten on the stdlib `sqlite3`
  module (Phase 0). The database file stays in `/var/lib/nhs-web/` — data lives
  outside the repo so a deploy can never clobber it, and the systemd sandbox
  keeps write access scoped to that one directory.
- **One thing nginx did that Caddy doesn't:** stock Caddy has no request rate
  limiting, so the brute-force protection on the login endpoint moves into the
  app (Phase 0).

---

## Phase 0 — code changes (local, then push)

- [ ] **Drop SQLAlchemy for stdlib `sqlite3`:**
  - `backend/app/database.py`: replace the engine/session machinery with a
    `get_db` FastAPI dependency that opens a `sqlite3.Connection` per request
    (`row_factory = sqlite3.Row`), applies the pragmas on connect
    (`journal_mode=WAL`, `foreign_keys=ON`, plus `busy_timeout=5000` so
    concurrent admin writes wait instead of erroring), and creates the schema
    at startup by executing `backend/migrations/001_init.sql`.
  - `backend/app/models.py`: delete — `migrations/001_init.sql` is now the one
    definition of the schema.
  - `backend/app/routers/events.py`: rewrite the queries as plain SQL
    (parameterized, never string-formatted).
  - `backend/app/config.py`: replace `database_url` with a plain
    `db_path: str` (env var `NHS_DB_PATH`), defaulting to `./calendar.db` for
    development.
  - `backend/requirements.txt`: remove `sqlalchemy`.
  - Update `backend/tests/` to match.

- [ ] **Add a login throttle to `backend/app/routers/auth.py`** — a small
  in-memory limiter (e.g. max 10 attempts per IP per minute → 429). This
  replaces nginx's `limit_req`, which has no stock-Caddy equivalent.

- [ ] **Replace `deploy/nginx/` with `deploy/caddy/Caddyfile`:**

  ```caddyfile
  pvnhs.com, www.pvnhs.com {
      root * /home/alex/GitHub/nhs-web/site
      encode gzip

      header X-Content-Type-Options nosniff
      header X-Frame-Options SAMEORIGIN
      header Referrer-Policy strict-origin-when-cross-origin

      request_body {
          max_size 2MB
      }

      handle /api/* {
          reverse_proxy 127.0.0.1:8000
      }

      handle {
          try_files {path} {path}.html {path}/
          file_server
      }
  }
  ```

  (TLS, HTTP→HTTPS redirect, and cert renewal are implicit — that's the point
  of Caddy.)

- [ ] **Update `deploy/systemd/nhs-api.service`:**
  - `WorkingDirectory` and `ExecStart` paths: `/srv/nhs-web` →
    `/home/alex/GitHub/nhs-web`
  - `ProtectHome=true` → `ProtectHome=read-only` (the service now reads its
    code and venv from `/home/alex`; writes still land only in
    `/var/lib/nhs-web` via `ReadWritePaths`).

- [ ] **Update `deploy/deploy.sh`:**
  - `REPO_DIR="/home/alex/GitHub/nhs-web"`
  - Generated env file: `NHS_DB_PATH=/var/lib/nhs-web/calendar.db` instead of
    `NHS_DATABASE_URL=…`
  - Add `chmod o+x /home/alex` next to the existing `chmod o+rx` lines.
  - Replace the nginx section with:
    ```bash
    cp "${REPO_DIR}/deploy/caddy/Caddyfile" /etc/caddy/Caddyfile
    caddy validate --config /etc/caddy/Caddyfile
    systemctl reload caddy
    ```

- [ ] Commit and push.

## Phase 1 — packages

- [ ] Caddy, from its official apt repo (the Ubuntu archive version lags):

  ```bash
  sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt update
  sudo apt install -y caddy python3-venv sqlite3
  ```

  (`sqlite3` is the CLI, for backups and poking at the database — the Python
  module is stdlib.)

## Phase 2 — update the checkout

- [ ] ```bash
  git -C /home/alex/GitHub/nhs-web pull
  ```

  That's the serving copy — there is no separate `/srv` checkout.

## Phase 3 — run the deployer

- [ ] First run — creates the `nhs` system user, venv, `/var/lib/nhs-web`,
  `/etc/nhs-web.env`, systemd unit, and Caddy config, then stops and asks for
  a password:

  ```bash
  sudo bash /home/alex/GitHub/nhs-web/deploy/deploy.sh
  ```

- [ ] Edit `/etc/nhs-web.env` and set the password you'll type into
  `admin.html`:

  ```bash
  NHS_ADMIN_PASSWORD=<admin password>
  ```

- [ ] Re-run the deployer (idempotent; never touches the env file again):

  ```bash
  sudo bash /home/alex/GitHub/nhs-web/deploy/deploy.sh
  ```

## Phase 4 — Cloudflare DNS

In the Cloudflare dashboard for pvnhs.com:

- [ ] `A` record `@` → `68.183.109.62`, **DNS only (grey cloud)**
- [ ] `CNAME` `www` → `pvnhs.com`, **DNS only (grey cloud)**

Grey cloud is required: Caddy proves domain ownership to Let's Encrypt by
answering on ports 80/443 itself. Behind Cloudflare's proxy that handshake
fails (and the proxy's own edge certificate would fight Caddy's). Once DNS
resolves to the droplet, Caddy fetches certificates automatically within
seconds of the first request — nothing to install, nothing to renew.

## Phase 5 — firewall

- [ ] ```bash
  sudo ufw allow OpenSSH
  sudo ufw allow 80/tcp     # ACME HTTP challenge + redirect to HTTPS
  sudo ufw allow 443/tcp
  sudo ufw enable
  ```

Uvicorn (127.0.0.1:8000) is already unreachable from outside.

## Phase 6 — verify

- [ ] ```bash
  curl -s https://pvnhs.com/api/health                          # {"status":"ok"}
  sudo sqlite3 /var/lib/nhs-web/calendar.db '.tables'           # events table exists after first start
  curl -sI http://pvnhs.com | head -1                           # 308 redirect to HTTPS
  ```
- [ ] Open `https://pvnhs.com/admin.html`, sign in, add an event.
- [ ] Confirm it appears on `https://pvnhs.com/calendar.html`.

---

## Ongoing

- **Deploying a change:** `git push` locally, then on the server:

  ```bash
  sudo bash /home/alex/GitHub/nhs-web/deploy/deploy.sh
  ```

  (It pulls, reinstalls deps, restarts the API, and reloads Caddy.)

- **Backups (do this once the site is live):** nightly SQLite online backup
  via cron, e.g. as root:

  ```
  0 3 * * * sqlite3 /var/lib/nhs-web/calendar.db ".backup /var/backups/nhs_calendar_$(date +\%a).db"
  ```

  (`.backup` is safe against a live WAL database; the day-of-week suffix keeps
  a rolling seven copies.)

- **Logs:** `journalctl -u nhs-api -f` for the API, `journalctl -u caddy -f`
  for Caddy.
