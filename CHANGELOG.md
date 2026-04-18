# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- BSD 2-Clause `LICENSE` at repo root.
- `CONTRIBUTORS.md` with maintainer list and contribution process.
- `CHANGELOG.md` (this file).
- GitHub Actions CI workflow at `.github/workflows/ci.yml` with lint, smoke-test, and docker-build jobs.
- `docs/configuration.md` documenting all runtime environment variables.
- `docs/deployment.md` with `docker run` quickstart and Kubernetes example.
- Module docstring in `monitor.py`.
- License / Contributing / Changelog / CI sections in `README.md`.

### Changed
- Dockerfile: fixed typos in ENV comments (`likle` → `like`, `teh` → `the`).
- `requirements.txt`: deduplicated the repeated `beautifulsoup4==4.10.0` entry.
- `.gitignore`: trimmed to Python/Docker-relevant entries; removed unrelated Go, Vagrant, and dotCloud rules.

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
