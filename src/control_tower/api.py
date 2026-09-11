from __future__ import annotations

import json
import os
from datetime import date
from urllib.request import Request, urlopen

from fastapi import FastAPI

from .alerts import alert_view, detect_alerts
from .config import DEFAULT_DB_PATH
from .db import database_ready

app = FastAPI(title="Check and Visit Operations Center Automation API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok" if database_ready(DEFAULT_DB_PATH) else "data_missing"}


@app.post("/alerts/run")
def run_alerts() -> dict:
    detected = detect_alerts(DEFAULT_DB_PATH, as_of=date.today())
    active = alert_view(DEFAULT_DB_PATH)
    severity_counts = active["severity"].value_counts().to_dict() if not active.empty else {}
    payload = {
        "evaluated_at": date.today().isoformat(),
        "active_conditions": int(len(detected)),
        "active_alerts": int(len(active)),
        "severity_counts": {str(key): int(value) for key, value in severity_counts.items()},
        "top_messages": active["message"].head(10).tolist() if not active.empty else [],
    }
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url and payload["active_alerts"]:
        request = Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=10) as response:  # noqa: S310 - operator-supplied URL
            payload["notification_status"] = response.status
    else:
        payload["notification_status"] = "not_configured"
    return payload


@app.get("/alerts/open")
def open_alerts(limit: int = 100) -> list[dict]:
    frame = alert_view(DEFAULT_DB_PATH).head(max(1, min(limit, 500)))
    return frame.where(frame.notna(), None).to_dict(orient="records")
