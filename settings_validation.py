"""Validate runtime settings payloads from the admin GUI (Pydantic v2)."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator

_email_adapter = TypeAdapter(EmailStr)


def _no_controls(value: str, label: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{label} must not contain control characters")
    return value


class RuntimeSettingsPayload(BaseModel):
    """POST /admin/api/settings body. Unknown keys (e.g. SMTP_*) are rejected."""

    model_config = ConfigDict(extra="forbid")

    website_url: str = Field(..., max_length=2048)
    website_url_2: str = Field(default="", max_length=2048)
    email_sender: EmailStr
    email_receiver1: EmailStr
    email_receiver2: str = Field(default="", max_length=320)
    email_receiver3: str = Field(default="", max_length=320)
    email_receiver4: str = Field(default="", max_length=320)

    @staticmethod
    def _require_http_url(u: str, label: str) -> str:
        _no_controls(u, label)
        if " " in u:
            raise ValueError(f"{label} must not contain spaces")
        parsed = urlparse(u)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"{label} must use http or https")
        if not parsed.netloc or not parsed.hostname:
            raise ValueError(f"{label} must include a host")
        # Credentials would be rendered on the status board and written to SETTINGS_FILE.
        if parsed.username is not None or parsed.password is not None:
            raise ValueError(f"{label} must not include userinfo credentials")
        return u

    @field_validator("website_url")
    @classmethod
    def _url_1(cls, v: str) -> str:
        u = v.strip()
        if not u:
            raise ValueError("WEBSITE_URL must not be empty")
        return cls._require_http_url(u, "WEBSITE_URL")

    @field_validator("website_url_2", mode="before")
    @classmethod
    def _url_2(cls, v: object) -> str:
        u = "" if v is None else str(v).strip()
        return cls._require_http_url(u, "WEBSITE_URL_2") if u else ""

    @field_validator("email_receiver2", "email_receiver3", "email_receiver4", mode="before")
    @classmethod
    def _optional_receiver(cls, v: object) -> str:
        s = "" if v is None else str(v).strip()
        if not s:
            return ""
        # Store the validated, normalized address rather than the raw input so
        # a display-name form with embedded newlines can never reach the To header.
        return str(_email_adapter.validate_python(s))
