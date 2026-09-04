# Sanitized production source backup

Snapshot date: 2026-09-04.

Source identity was verified against `/home/hermes/alfa_sync` in LXC 107 by SHA-256 before copying from the matching local candidate.

Included: Dockerfile, base Compose file, requirements, documentation, scraper/sync modules and synthetic/manual test modules.

Excluded intentionally:

- `app/tg_bot.py` because production contains an embedded credential. Its production SHA-256 is `2a658a83722dc052d1a96e91673f4011b9ddaf3c2224eddbddb79256cbc0119b` and the full file remains in the server-side backup only.
- `docker-compose.logging.yml` because it exists only on the server. Its SHA-256 is `b3fc69a8c8034fcb171fe8ec10ea7a5c42f98d93fb399ba2fe5a96b7020ee3c5` and it remains in the server-side backup.
- `auth/`, runtime JSON/ICS, cookies, databases, debug artifacts, virtual environments and real user data.

Full server-side rollback copy: `/home/hermes/alfa_sync-releases/production-backup-20260904-1522`.
