# Configuration

`site-checker` is configured entirely through environment variables, read at startup by [`monitor.py`](../monitor.py).

## Environment variables

| Variable          | Required | Default | Description |
| ----------------- | :------: | ------- | ----------- |
| `WEBSITE_URL`     | yes      | _none_  | Full URL of the page to monitor (e.g. `https://example.com/passports`). |
| `EMAIL_SENDER`    | yes      | _none_  | Verified sender address in your SMTP provider (for AWS SES, an identity with DKIM set up). |
| `EMAIL_RECEIVER1` | yes      | _none_  | Primary notification recipient. |
| `EMAIL_RECEIVER2` | no\*     | _none_  | Secondary notification recipient. \*Currently referenced unconditionally in `monitor.py`; leave it set to a valid address or the same as `EMAIL_RECEIVER1`. |
| `SMTP_USERNAME`   | yes      | _none_  | SMTP auth username (AWS SES SMTP credential). |
| `SMTP_PASSWORD`   | yes      | _none_  | SMTP auth password (AWS SES SMTP credential). |
| `SMTP_PORT`       | no       | `587`   | Reserved for future use — `monitor.py` currently connects to port `465` (SMTPS) against `email-smtp.us-east-1.amazonaws.com`. |
| `TZ`              | no       | `America/Denver` | Container timezone, used for timestamps in log lines and email body. |

## Check interval

The poll interval is currently hard-coded to **300 seconds** in [`monitor.py`](../monitor.py). Changing it requires an edit + rebuild; exposing it as an env var is tracked in [CHANGELOG.md](../CHANGELOG.md) `Unreleased` wishlist.

## Example `.env`

```dotenv
WEBSITE_URL=https://example.com/passports
EMAIL_SENDER=alerts@example.com
EMAIL_RECEIVER1=me@example.com
EMAIL_RECEIVER2=backup@example.com
SMTP_USERNAME=AKIA...
SMTP_PASSWORD=BK...
TZ=America/Denver
```

Never commit a real `.env`. The repo's [`.gitignore`](../.gitignore) already excludes `.env`.

## SMTP provider notes

The script is written against **AWS SES** and hard-codes the `email-smtp.us-east-1.amazonaws.com` endpoint. To use another provider or region you currently need to edit `monitor.py` directly.

## Logs

Logs are written both to **stderr** (container stdout/stderr) and to `/var/log/site-checker.log` inside the container. When running in Kubernetes, stderr is the canonical source — prefer `kubectl logs` over mounting the log file.
