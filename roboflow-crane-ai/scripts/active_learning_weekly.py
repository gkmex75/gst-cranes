#!/usr/bin/env python3
"""
Active learning weekly cron.

Pulls last 7 days of identify_logs from map.gstcranes.com's D1 database,
filters to rows where:
  - cascade_source is roboflow-* AND user changed final_brand/final_model
    away from the autofill (correction signal), OR
  - top_confidence < 0.4 (low confidence — model uncertain), OR
  - top_class is null (Roboflow disagreed/skipped, Vision fallback used)

Generates an HTML review page and (when SMTP configured) emails the
operator. Once a human labels the queue, the corrections drive the
monthly Roboflow retrain.

Pre-req: wrangler authenticated as gstcranes@gmail.com (`wrangler whoami`).

Usage:
  python3 active_learning_weekly.py weekly  # generate this week's review queue
  python3 active_learning_weekly.py retrain # trigger Roboflow retrain (1st of month)
"""

import json
import os
import smtplib
import subprocess
import sys
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).parent.parent
QUEUE_DIR = ROOT / "outputs/review_queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

D1_DATABASE = "crane-directory"  # name in wrangler.toml of the directory app
WRANGLER_DIR = Path.home() / "projects/crane-rental-directory"


def current_week_key() -> str:
    return datetime.now().strftime("%Y-W%V")


def query_d1(sql: str) -> list[dict]:
    """Run a SQL query against the production D1 via wrangler."""
    result = subprocess.run(
        ["npx", "wrangler", "d1", "execute", D1_DATABASE, "--remote", "--json", "--command", sql],
        capture_output=True,
        text=True,
        cwd=WRANGLER_DIR,
    )
    if result.returncode != 0:
        print(f"[!] D1 query failed: {result.stderr[:500]}", file=sys.stderr)
        return []
    try:
        # wrangler output is [{results: [...], success: ..., meta: ...}]
        data = json.loads(result.stdout)
        if isinstance(data, list) and data and "results" in data[0]:
            return data[0]["results"]
        return []
    except json.JSONDecodeError as e:
        print(f"[!] D1 JSON parse failed: {e}\n{result.stdout[:500]}", file=sys.stderr)
        return []


def collect_review_queue() -> list[dict]:
    cutoff = int((datetime.now() - timedelta(days=7)).timestamp())
    # Pull rows with disagreement OR low confidence
    sql = f"""
        SELECT id, r2_key, top_class, top_confidence, predictions_json, cascade_source,
               final_brand, final_model, listing_id, created_at, finalized_at
          FROM identify_logs
         WHERE created_at >= {cutoff}
           AND (
             top_confidence < 0.4
             OR top_class IS NULL
             OR (final_brand IS NOT NULL AND cascade_source LIKE 'roboflow-%' AND top_class NOT LIKE '%' || REPLACE(LOWER(final_brand), '-', '_') || '%')
           )
         ORDER BY created_at DESC
         LIMIT 200
    """
    return query_d1(sql)


def write_labeller_page(entries: list[dict], out_path: Path):
    rows = []
    for i, e in enumerate(entries):
        preds = e.get("predictions_json")
        try:
            preds_data = json.loads(preds) if preds else []
        except Exception:
            preds_data = []
        preds_str = ", ".join(
            f"{p.get('class', '?')}@{float(p.get('confidence', 0)):.2f}" for p in preds_data[:3]
        )
        photo_url = f"https://map.gstcranes.com/cdn-cgi/image/width=240/{e.get('r2_key', '')}"
        autofill = f"{e.get('top_class') or '(no roboflow signal)'} @ {float(e.get('top_confidence') or 0):.2f}"
        user_final = f"{e.get('final_brand') or '?'} {e.get('final_model') or '?'}".strip()
        rows.append(
            f"""<tr><td><img src="{photo_url}" loading="lazy" style="max-width:240px"></td>
                    <td><div><b>Autofill:</b> {autofill}</div><div><b>User saved:</b> {user_final}</div><div style="color:#888;font-size:11px">top-3: {preds_str}</div><div style="color:#888;font-size:11px">cascade: {e.get('cascade_source','?')}</div></td>
                    <td><input name="brand_{i}" value="{e.get('final_brand') or ''}" style="width:140px" placeholder="Brand"></td>
                    <td><input name="model_{i}" value="{e.get('final_model') or ''}" style="width:180px" placeholder="Model"></td>
                    <td><input name="r2_{i}" type="hidden" value="{e.get('r2_key','')}"><textarea name="notes_{i}" rows="2" cols="30"></textarea></td></tr>"""
        )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Crane Review Queue {current_week_key()}</title>
<style>
  body{{font-family:-apple-system,sans-serif;margin:24px;background:#fafafa;color:#222}}
  h1{{margin:0 0 6px}}
  p.sub{{color:#666;margin-top:0}}
  table{{border-collapse:collapse;background:white;width:100%}}
  td,th{{padding:10px;border:1px solid #e0e0e0;vertical-align:top;font-size:13px}}
  th{{background:#f4f4f4;text-align:left}}
  input,textarea{{font-family:inherit;font-size:13px;padding:4px}}
  button{{padding:10px 24px;background:#1a73e8;color:white;border:0;border-radius:6px;font-weight:600;font-size:14px;cursor:pointer}}
</style>
</head><body>
<h1>Crane Review Queue · {current_week_key()}</h1>
<p class="sub">{len(entries)} photos flagged for review. Correct the brand+model if wrong, leave blank to skip.</p>
<form method="POST" action="https://map.gstcranes.com/api/active-learning/save-review">
<table>
<thead><tr><th>Photo</th><th>AI prediction + user save</th><th>Correct brand</th><th>Correct model</th><th>Notes</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p style="margin-top:20px"><button type="submit">Save corrections (queues for Roboflow upload)</button></p>
</form>
</body></html>"""
    out_path.write_text(html)


def send_email(to_addr: str, subject: str, body: str, link: str | None = None):
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "active-learning@gstcranes.com")
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body + (f"\n\nReview here: {link}" if link else ""))
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"[!] No SMTP_HOST configured — would have emailed: {subject}")
        return
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        if user:
            s.login(user, password or "")
        s.send_message(msg)


def weekly():
    entries = collect_review_queue()
    print(f"[weekly] {len(entries)} entries flagged in last 7 days")
    if not entries:
        return
    week = current_week_key()
    out = QUEUE_DIR / f"reviewer_{week}.html"
    write_labeller_page(entries, out)
    print(f"[weekly] Wrote: {out}")
    link = os.environ.get("REVIEW_BASE_URL", "file://") + str(out)
    send_email(
        os.environ.get("REVIEW_TO", "gokmen@gstcranes.com"),
        f"Crane review queue — {len(entries)} photos · {week}",
        f"{len(entries)} uploads flagged for review. ~10-15 minutes of labeling adds a fresh batch to the training corpus.",
        link=link,
    )


def retrain():
    key = os.environ.get("ROBOFLOW_API_KEY")
    if not key:
        env = (Path.home() / "gst-cranes/.env").read_text()
        for line in env.splitlines():
            if line.startswith("ROBOFLOW_API_KEY="):
                key = line.split("=", 1)[1].strip()
                break
    if not key:
        print("[retrain] No ROBOFLOW_API_KEY")
        return

    import requests
    from roboflow import Roboflow

    rf = Roboflow(api_key=key)
    project = rf.workspace("gokmens-workspace").project("crane-recognition-v1-idh46")

    print("[retrain] Generating new version with current corpus...")
    new_version = project.generate_version(
        {
            "preprocessing": {
                "auto-orient": True,
                "resize": {"width": 640, "height": 640, "format": "Fit (white edges) in"},
            },
            "augmentation": {
                "flip": {"horizontal": True, "vertical": False},
                "brightness": {"brighten": True, "darken": True, "percent": 20},
                "rotate": {"degrees": 12},
                "image": {"versions": 3},
            },
        }
    )
    print(f"[retrain] Generated version {new_version}")

    v = project.version(int(new_version))
    v.export("folder")
    r = requests.post(
        f"https://api.roboflow.com/gokmens-workspace/crane-recognition-v1-idh46/{new_version}/train?api_key={key}&nocache=true",
        json={"modelType": "resnet50"},  # ResNet50 finishes within free plan's compute window
    )
    print(f"[retrain] Train trigger: HTTP {r.status_code}")
    Path(ROOT / "state/training_state.json").write_text(
        json.dumps(
            {
                "version": str(new_version),
                "model_type": "resnet50",
                "retrained_at": time.time(),
            },
            indent=2,
        )
    )


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "weekly"
    if cmd == "weekly":
        weekly()
    elif cmd == "retrain":
        retrain()
    else:
        print(f"Usage: {sys.argv[0]} [weekly|retrain]")
        sys.exit(1)


if __name__ == "__main__":
    main()
