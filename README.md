# Pine View School NHS

Chapter website for the Pine View School National Honor Society. A static site
plus a small FastAPI service that backs the editable calendar.

Modernized rebuild of <https://pvsnhs.wixsite.com/pine-view-school-nhs>.

## Layout

```
site/                  Everything Caddy serves. No build step, no framework.
  index.html           Home — about, four pillars, requirements, timeline, FAQ, contact
  calendar.html        Public calendar, rendered from the API
  admin.html           Calendar editor (password-gated, noindex)
  member-information.html
  board.html
  file-share.html
  assets/css/style.css     Design system (pastel blue / pastel yellow / white)
  assets/css/calendar.css  Calendar + admin additions only
  assets/js/main.js        Nav, scroll reveal, eligibility checker, meeting status
  assets/js/api.js         The one place that knows where the API lives
  assets/js/calendar.js    Public calendar rendering
  assets/js/admin.js       Login, create / edit / delete
  documents/           Chapter PDFs (gitignored — see below)

backend/               FastAPI. Owns /api/* and nothing else.
  app/main.py          App, CORS, router mounting
  app/config.py        Settings from NHS_* env vars
  app/database.py      sqlite3 connections, pragmas, get_db dependency
  app/schemas.py       Request/response models — the API contract
  app/auth.py          Shared-password admin auth (see its docstring)
  app/routers/         events.py, auth.py
  migrations/          001_init.sql — the schema, executed at startup
  tests/               pytest

deploy/                Caddyfile, systemd unit, deploy.sh
scripts/dev.sh         Runs both servers locally
```

## Run it locally

```bash
./scripts/dev.sh
```

- Site: <http://127.0.0.1:8000>
- API docs: <http://127.0.0.1:8001/api/docs>
- Admin: <http://127.0.0.1:8000/admin.html>, password `dev`

The first run creates `backend/.venv` and installs dependencies. Two ports is
deliberate — it mirrors production, where Caddy serves the files and uvicorn
only answers `/api`, so nothing can quietly come to depend on FastAPI serving
HTML. `assets/js/api.js` notices port 8000 and targets 8001 automatically.

Tests:

```bash
cd backend && ./.venv/bin/python -m pytest
```

## Architecture, in one paragraph

Caddy serves `site/` straight from the git checkout at
`/home/alex/GitHub/nhs-web`, terminates TLS with certificates it obtains and
renews itself, and proxies `/api/` to uvicorn on `127.0.0.1:8000`. They are
separate on purpose: if the API process
dies, every page still loads and the calendar shows "temporarily unavailable"
instead of the whole site going down. Same-origin proxying also means the
browser never issues a cross-origin request in production, so CORS is a
dev-only concern. Data is SQLite at `/var/lib/nhs-web/calendar.db` — one writer,
a few hundred rows a year, accessed through the stdlib `sqlite3` module — no
ORM, no reason for anything heavier.

## The calendar

`GET /api/events` is public. Everything that writes needs an admin token.

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/events` | — | Published events, date order. Optional `start`/`end` filters. |
| `GET` | `/api/events/{id}` | — | One published event. |
| `GET` | `/api/events/all` | admin | Includes unpublished drafts. |
| `POST` | `/api/events` | admin | Create. |
| `PATCH` | `/api/events/{id}` | admin | Update; send only changed fields. |
| `DELETE` | `/api/events/{id}` | admin | Delete. |
| `POST` | `/api/auth/login` | — | Password in, bearer token out. |
| `GET` | `/api/health` | — | Liveness. |

To update the calendar: open `/admin.html`, sign in, use the form. Unchecking
**Published** saves a draft that only the admin list shows — useful for staging
next year's schedule.

Dates are stored as a plain date plus optional plain times, not as UTC
timestamps. A chapter meeting is "1:10 pm at school", a wall-clock fact; storing
an instant would make it drift across daylight-saving boundaries.

### Auth is deliberately minimal

One shared password, an HMAC-signed token in `sessionStorage`, no user accounts.
That fits a chapter with one or two officers editing a calendar, and it's the
first thing to replace if that stops being true. Read the docstring at the top
of `backend/app/auth.py` before changing it — it lists what the scheme does and
doesn't protect against. Failed logins are rate-limited in the API itself
(`app/routers/auth.py`) — Caddy has no `limit_req` equivalent to lean on.

If both `NHS_ADMIN_PASSWORD` and `NHS_SECRET_KEY` are unset, every write
endpoint returns 503. That is intentional: a half-configured server fails
closed rather than accepting anonymous edits.

## Deploying

The server is Ubuntu 24.04, serving from the checkout at
`/home/alex/GitHub/nhs-web`. See `DEPLOYMENT.md` for the full first-time
walkthrough (Caddy's apt repo, DNS, firewall); the short version:

```bash
sudo apt install -y caddy python3-venv git            # caddy from its official apt repo
git clone git@github.com:shoffalex/nhs-web.git ~/GitHub/nhs-web
sudo bash ~/GitHub/nhs-web/deploy/deploy.sh   # creates user, dirs, venv, /etc/nhs-web.env
sudo nano /etc/nhs-web.env                    # set NHS_ADMIN_PASSWORD
sudo bash ~/GitHub/nhs-web/deploy/deploy.sh   # re-run to pick it up
```

Afterwards, a deploy is just:

```bash
sudo bash /home/alex/GitHub/nhs-web/deploy/deploy.sh
```

It's idempotent, never overwrites `/etc/nhs-web.env`, and won't touch the
database. Logs: `journalctl -u nhs-api -f` and `journalctl -u caddy -f`.

TLS needs no ceremony: Caddy fetches and renews the Let's Encrypt certificate
itself, provided the Cloudflare DNS records stay **DNS-only (grey cloud)** so
the ACME challenge reaches the droplet directly.

## Member documents

`site/documents/*` is gitignored. The chapter file library is members-only, and
a public GitHub repo would make those PDFs permanently fetchable and indexable
even after a delete. Copy them to the server directly instead:

```bash
rsync -av ./local-pdfs/ digitalocean:GitHub/nhs-web/site/documents/
```

If you make this repo private and would rather version them, drop those two
lines from `.gitignore`.

## Color scheme

| Role | Token | Value |
| --- | --- | --- |
| Pastel blue (surface) | `--blue-100` | `#e2eefb` |
| Pastel blue (accent) | `--blue-300` | `#a5c9ee` |
| Blue (text/buttons) | `--blue-600` | `#35679f` |
| Pastel yellow (surface) | `--yellow-100` | `#fdf6dc` |
| Pastel yellow (accent) | `--yellow-300` | `#f7dd85` |
| White / paper | `--white` / `--paper` | `#ffffff` / `#fbfdff` |

Deeper blues carry text and buttons so contrast stays readable — pastels alone
can't meet WCAG AA on white. All colors are CSS custom properties at the top of
`assets/css/style.css`; change them there and the whole site follows.

## Updating content

- **Calendar** — use `/admin.html`. Nothing to edit by hand.
- **Board members** — edit the `<article class="person">` blocks in `board.html`.
  Add `class="person is-lead"` for yellow accent styling.
- **Documents** — put the file in `site/documents/`, then convert that row in
  `file-share.html` from a `<div class="file-row">` to
  `<a class="file-row" href="documents/name.pdf">` and change the
  `pill is-mute` "Not uploaded" badge to `pill` "Download".
- **Contact details** — footers on every page, plus the contact section of
  `index.html`.

## Known loose ends

- `member-information.html` still has the 2025–26 meeting dates hardcoded as
  `<li class="meet" data-date="…">`. Now that events come from the API, that
  page should fetch them too, or the two schedules will drift. `calendar.js`
  shows the pattern; `NHS.markMeetings()` is shared between them.
- Board names and the meeting schedule were copied from the live site as of
  August 2026 and need refreshing each school year.
- The file-share rows are marked "Not uploaded" because the original library is
  members-only; nothing links to a document that doesn't exist yet.
