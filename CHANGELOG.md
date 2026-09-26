# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Admin GUI served on port 8080 (FastAPI, server-rendered, instrument-panel theme): heartbeat home page with expandable recent checks, `/admin` status board, and token-gated `/admin/settings` for URLs and recipients (`SITE_CHECKER_ADMIN_TOKEN`).
- Optional `SETTINGS_FILE` persistence for GUI saves (atomic write, mode 0600, overrides env on restart).
- `/healthz` liveness endpoint tied to the monitor loop heartbeat, and a Docker `HEALTHCHECK` that uses it.
- Optional `WEBSITE_URL_2` and `EMAIL_RECEIVER3`/`EMAIL_RECEIVER4`; new `CHECK_INTERVAL_SECONDS`, `SMTP_HOST`, `ADMIN_*` and `LOG_FILE` settings.
- pytest suite (settings validation/store, admin API, monitor loop), `requirements-dev.txt`, `ruff.toml`.
- BSD 2-Clause `LICENSE` at repo root.
- `CONTRIBUTORS.md` with maintainer list and contribution process.
- `CHANGELOG.md` (this file).
- GitHub Actions CI workflow at `.github/workflows/ci.yml` with lint, smoke-test, and docker-build jobs.
- `docs/configuration.md` documenting all runtime environment variables.
- `docs/deployment.md` with `docker run` quickstart and Kubernetes example.
- Module docstring in `monitor.py`.
- License / Contributing / Changelog / CI sections in `README.md`.

### Changed
- Monitor loop: HTTP fetches now have a (10s connect, 30s read) timeout and SMTP a 30s timeout. A startup fetch failure no longer exits the process. Unexpected errors are logged and the loop continues.
- A change's baseline only advances after the alert email is accepted, so a failed send is retried on the next poll instead of lost.
- Dockerfile: runs as non-root uid 10001, exposes 8080, and installs only `tzdata` (no `dist-upgrade`). The placeholder SMTP credential `ENV` lines are removed from the image.
- `requirements.txt`: dropped the unused `beautifulsoup4`/`soupsieve` pins and the legacy `urllib3<1.27` pin, and moved to `requests>=2.32.4`.
- CI: ruff is pinned with an explicit rule set, a real pytest job replaces the placeholder, and the image build now runs a container smoke test against the GUI.
- Dockerfile: fixed typos in ENV comments (`likle` → `like`, `teh` → `the`).
- `requirements.txt`: deduplicated the repeated `beautifulsoup4==4.10.0` entry.
- `.gitignore`: trimmed to Python/Docker-relevant entries; removed unrelated Go, Vagrant, and dotCloud rules.

### Fixed
- `send_email` raised `TypeError` (`", ".join([...None])`) when `EMAIL_RECEIVER2` was unset, which crashed the monitor on the first detected change.
- Logging no longer fails at import when `/var/log` is not writable.

### Removed
- Dockerfile: commented-out `RUN apt-get install htop -y` line.

## [0.1.0] - 2025-01-01

### Added
- `monitor.py`: periodic hash-based change detection with SMTP (AWS SES) notifications.
- `Dockerfile` based on `python:3.11-slim-bookworm`.
- GitLab CI pipeline (`.gitlab-ci.yml`) with Kaniko image build, SAST, container scan, and secret detection.
- `README.md` describing the problem, technology, and deployment options.

[Unreleased]: https://github.com/andreab67/site-checker/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/andreab67/site-checker/releases/tag/v0.1.0
