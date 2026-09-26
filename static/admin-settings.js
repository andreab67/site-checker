(function () {
  "use strict";
  const form = document.getElementById("runtime-settings-form");
  if (!form) {
    return;
  }
  const msg = document.getElementById("settings-msg");

  function value(id) {
    const el = document.getElementById(id);
    return el ? el.value.trim() : "";
  }

  function show(text, kind) {
    msg.textContent = text;
    msg.className = "settings-msg" + (kind ? " settings-msg--" + kind : "");
  }

  form.addEventListener("submit", async function (ev) {
    ev.preventDefault();
    const token = value("admin-token");
    if (!token) {
      show("Paste the admin token (SITE_CHECKER_ADMIN_TOKEN).", "err");
      return;
    }
    const body = {
      website_url: value("f-url"),
      website_url_2: value("f-url-2"),
      email_sender: value("f-sender"),
      email_receiver1: value("f-r1"),
      email_receiver2: value("f-r2"),
      email_receiver3: value("f-r3"),
      email_receiver4: value("f-r4"),
    };
    show("Saving…");
    try {
      const r = await fetch("/admin/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Admin-Token": token },
        body: JSON.stringify(body),
      });
      let data = {};
      try {
        data = await r.json();
      } catch (ignore) {
        data = {};
      }
      if (!r.ok) {
        const detail = data.detail;
        let text = r.status + " " + (r.statusText || "Request failed");
        if (typeof detail === "string") {
          text = detail;
        } else if (Array.isArray(detail)) {
          text = detail
            .map(function (d) {
              const loc = Array.isArray(d.loc) ? d.loc.join(".") : "";
              return (loc ? loc + ": " : "") + (d.msg || JSON.stringify(d));
            })
            .join("; ");
        }
        show(text, "err");
        return;
      }
      show(
        data.persisted
          ? "Saved to SETTINGS_FILE and applied. The monitor uses these values from its next poll."
          : "Applied in memory. The monitor uses these values from its next poll; they reset on restart (no SETTINGS_FILE).",
        "ok"
      );
    } catch (e) {
      show(String(e), "err");
    }
  });
})();
