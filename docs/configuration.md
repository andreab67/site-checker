# Configuration

`site-checker` is configured through environment variables read at startup by [`monitor.py`](../monitor.py). The URL and recipient settings can also be changed at runtime from the [admin GUI](#admin-gui).

## Environment variables

### Monitoring and alerts

| Variable                 | Required | Default | Description |
| ------------------------ | :------: | ------- | ----------- |
| `WEBSITE_URL`            | yes\*    | _none_  | Full `http(s)` URL of the page to monitor. \*Can instead be set from the admin GUI; with no valid URL the container idles and says so on the status board. |
| `WEBSITE_URL_2`          | no       | _none_  | Optional second page, monitored with its own baseline. |
| `EMAIL_SENDER`           | yes      | _none_  | Verified sender address in your SMTP provider (for AWS SES, an identity with DKIM set up). |
| `EMAIL_RECEIVER1`        | yes      | _none_  | Primary notification recipient. |
| `EMAIL_RECEIVER2`–`4`    | no       | _none_  | Additional recipients. Empty slots are skipped. |
| `SMTP_USERNAME`          | yes      | _none_  | SMTP auth username (AWS SES SMTP credential). |
| `SMTP_PASSWORD`          | yes      | _none_  | SMTP auth password (AWS SES SMTP credential). |
| `SMTP_HOST`              | no       | `email-smtp.us-east-1.amazonaws.com` | SMTPS host. The connection is implicit TLS on port **465**. |
| `CHECK_INTERVAL_SECONDS` | no       | `300`   | Seconds between polls. Values under 30 are raised to 30. |
| `TZ`                     | no       | `America/Denver` | Timezone for log lines, GUI timestamps, and the email body. |

### Admin GUI

| Variable                   | Required | Default   | Description |
| -------------------------- | :------: | --------- | ----------- |
| `SITE_CHECKER_ADMIN_TOKEN` | no       | _none_    | Shared secret for saving settings from the GUI. Unset means the GUI is read-only (saves return `503`). Store it with the SMTP credentials, not in the image. |
| `SETTINGS_FILE`            | no       | _none_    | JSON file that GUI saves are written to (atomically, mode `0600`). When present at startup, its values override the matching environment variables. Unset means saves apply in memory only and are lost on restart. Use `/data/settings.json` with a volume mounted at `/data`. |
| `ADMIN_ENABLED`            | no       | `1`       | Set to `0` to run without the web server. |
| `ADMIN_HOST`               | no       | `0.0.0.0` | Bind address for the GUI. |
| `ADMIN_PORT`               | no       | `8080`    | Port for the GUI. |
| `LOG_FILE`                 | no       | `/var/log/site-checker.log` | Extra log file. Skipped silently when not writable, which is the case for the non-root image; set to an empty value to disable. |

## Admin GUI

The container serves a small web UI on `ADMIN_PORT`:

| Path               | What it shows |
| ------------------ | ------------- |
| `/`                | Heartbeat of the monitor loop and the last 16 checks. Each check opens to show the HTTP status, response time, body size, full MD5, and any error. |
| `/admin`           | Status board: the last poll, the last detected change, the result of the last alert email, and the live configuration. SMTP credentials are only ever shown as configured or missing. |
| `/admin/settings`  | Form to change the URLs and recipients. Requires `SITE_CHECKER_ADMIN_TOKEN`. |
| `/healthz`         | JSON liveness. Returns `503` when the monitor loop has not completed an iteration within `2 × CHECK_INTERVAL_SECONDS + 180` seconds, which catches a hung fetch or SMTP session. The web thread being up is not enough for it to pass. |

Settings posted from the GUI are validated before they are used. URLs must be `http(s)` with a host, no embedded credentials, and no whitespace or control characters. Addresses are normalized, and unknown keys such as `SMTP_PASSWORD` are rejected. The monitor picks up the new values on its next poll. A new or changed URL gets a fresh baseline and does not trigger an alert.

The GUI has no user accounts. Anyone who can reach it can read the configured URLs and addresses, and anyone with the token can change them. Keep it on a private network, behind an authenticating reverse proxy, or port-forwarded (`kubectl port-forward`). Always use TLS when it crosses a network.

## Alert behaviour

- The first successful fetch of each URL records its baseline. No email is sent for it.
- A different MD5 on a later poll sends one email to every configured recipient.
- The baseline only moves forward after the SMTP server accepts the email. If a send fails, the alert is retried on the next poll instead of being dropped. The failure is shown on the status board.
- A failed fetch never resets a baseline.

## Example `.env`

```dotenv
WEBSITE_URL=https://example.com/passports
EMAIL_SENDER=alerts@example.com
EMAIL_RECEIVER1=me@example.com
EMAIL_RECEIVER2=backup@example.com
SMTP_USERNAME=AKIA...
SMTP_PASSWORD=BK...
SITE_CHECKER_ADMIN_TOKEN=change-me-to-a-long-random-string
SETTINGS_FILE=/data/settings.json
TZ=America/Denver
```

Never commit a real `.env`. The repo's [`.gitignore`](../.gitignore) already excludes `.env`.

## SMTP provider notes

The defaults target **AWS SES** in `us-east-1`. For another SES region or provider, set `SMTP_HOST`. The provider must offer SMTPS (implicit TLS) on port 465. STARTTLS on 587 is not supported.

## Logs

Logs go to **stderr** (container stdout/stderr). They also go to `LOG_FILE` when that path is writable. In Kubernetes, `kubectl logs` is the canonical source.
