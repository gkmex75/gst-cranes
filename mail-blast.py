# mail-blast.py
# SP4 Hetzner SMTP blast for opt-in list. Loaded by promote-api/runners/email_blast.py.
import os, smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def blast(subject: str, html_body: str, text_body: str, recipients: list[str]) -> dict:
    if len(recipients) == 0:
        raise ValueError("no recipients")
    smtp_host = os.environ["HETZNER_SMTP_HOST"]
    smtp_port = int(os.environ.get("HETZNER_SMTP_PORT", 587))
    smtp_user = os.environ["HETZNER_SMTP_USER"]
    smtp_pass = os.environ["HETZNER_SMTP_PASS"]
    from_addr = os.environ.get("HETZNER_FROM_ADDR", "blast@geocra.com")

    sent = 0
    failed: list[tuple[str, str]] = []
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(smtp_user, smtp_pass)
        for rcpt in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = rcpt
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            try:
                s.sendmail(from_addr, [rcpt], msg.as_string())
                sent += 1
            except Exception as e:
                failed.append((rcpt, str(e)))
    return {"sent_count": sent, "failed": failed}
