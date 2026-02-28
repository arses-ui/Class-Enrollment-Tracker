#!/usr/bin/env python3
"""
Dartmouth Course Seat Monitor
Watches COSC 031 (Algorithms) CRN 31322 for an open seat.
Sends a macOS notification + email when enrollment drops below the limit.
"""

import requests
from bs4 import BeautifulSoup
import subprocess
import smtplib
from email.mime.text import MIMEText
import time
import threading
import logging
import sys
from datetime import datetime
from config import EMAIL_ADDRESS, EMAIL_APP_PASSWORD, FRIEND_EMAILS

# ── Configuration ────────────────────────────────────────────────────────────
TARGET_CRN = "31322"
COURSE_NAME = "COSC 031 - Algorithms"
TERM = "202603"
DEPT = "COSC"

CHECK_INTERVAL_SECONDS = 5 * 60  # 5 minutes
MAX_BACKOFF_SECONDS = 30 * 60    # 30 minutes max on repeated failures
FRIEND_DELAY_SECONDS = 2 * 60    # 2 minutes delay before notifying friends


TIMETABLE_URL = "https://oracle-www.dartmouth.edu/dart/groucho/timetable.display_courses"

FORM_DATA = {
    "distribradio": "alldistribs",
    "subjectradio": "selectsubjects",
    "termradio": "selectterms",
    "hoursradio": "allhours",
    "periods": "no_value",
    "distribs": "no_value",
    "distribs_i": "no_value",
    "distribs_wc": "no_value",
    "distribs_lang": "no_value",
    "sortorder": "dept",
    "deliveryradio": "alldelivery",
    "deliverymodes": "no_value",
    "pmode": "public",
    "term": "",
    "levl": "",
    "fys": "n",
    "wrt": "n",
    "pe": "n",
    "review": "n",
    "crnl": "no_value",
    "classyear": "2008",
    "searchtype": "Subject Area(s)",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0.0.0 Safari/537.36",
}

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log"),
    ],
)
log = logging.getLogger(__name__)


def send_email(title: str, message: str, recipients: list[str] | None = None):
    """Send an email notification via Gmail SMTP."""
    if recipients is None:
        recipients = [EMAIL_ADDRESS]
    try:
        msg = MIMEText(f"{message}\n\nGo enroll now!\nhttps://oracle-www.dartmouth.edu/dart/groucho/timetable.main")
        msg["Subject"] = title
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = ", ".join(recipients)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.send_message(msg)
        log.info("Email notification sent to %s", ", ".join(recipients))
    except Exception as e:
        log.warning("Failed to send email to %s: %s", ", ".join(recipients), e)


def send_delayed_friend_emails(title: str, message: str):
    """Wait a few minutes then email friends."""
    time.sleep(FRIEND_DELAY_SECONDS)
    send_email(title, message, FRIEND_EMAILS)


def notify(title: str, message: str):
    """Send a macOS desktop notification + email."""
    # macOS notification
    subprocess.run([
        "osascript", "-e",
        f'display notification "{message}" with title "{title}" sound name "Glass"'
    ])
    # Email notification (you first)
    send_email(title, message)
    # Email friends after a delay (runs in background so it doesn't block)
    threading.Thread(target=send_delayed_friend_emails, args=(title, message), daemon=True).start()


def fetch_enrollment() -> tuple[int, int] | None:
    """
    Fetch the timetable page and return (enrollment, limit) for the target CRN.
    Returns None if the course isn't found or there's a parse error.
    """
    data = dict(FORM_DATA)
    # requests needs lists for repeated keys
    data["terms"] = ["no_value", TERM]
    data["depts"] = ["no_value", DEPT]

    resp = requests.post(TIMETABLE_URL, data=data, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find all <td> cells; walk through looking for our CRN
    cells = soup.find_all("td")
    for i, cell in enumerate(cells):
        if cell.get_text(strip=True) == TARGET_CRN:
            # The table columns after CRN are:
            # CRN, Subj, Num, Sec, Title, Text, Xlist, Period Code, Period,
            # Room, Building, Instructor, WC, Dist, Lang Req, Lim, Enrl, ...
            # That's CRN at index i, Lim at i+15, Enrl at i+16
            try:
                lim_text = cells[i + 15].get_text(strip=True)
                enrl_text = cells[i + 16].get_text(strip=True)
                return int(enrl_text), int(lim_text)
            except (IndexError, ValueError) as e:
                log.warning("Found CRN %s but failed to parse Enrl/Lim: %s", TARGET_CRN, e)
                return None

    log.warning("CRN %s not found in timetable response", TARGET_CRN)
    return None


def run():
    log.info("Starting seat monitor for %s (CRN %s)", COURSE_NAME, TARGET_CRN)
    log.info("Checking every %d seconds", CHECK_INTERVAL_SECONDS)

    consecutive_failures = 0
    notified = False

    while True:
        try:
            result = fetch_enrollment()

            if result is None:
                consecutive_failures += 1
                wait = min(CHECK_INTERVAL_SECONDS * (2 ** consecutive_failures), MAX_BACKOFF_SECONDS)
                log.error("Failed to fetch data. Retrying in %d seconds.", wait)
                time.sleep(wait)
                continue

            consecutive_failures = 0
            enrl, lim = result
            log.info("%s — Enrolled: %d / Limit: %d", COURSE_NAME, enrl, lim)

            if enrl < lim:
                spots = lim - enrl
                msg = f"{spots} spot(s) open! Enrolled: {enrl}/{lim}"
                log.info("*** SPOT AVAILABLE *** %s", msg)
                notify(f"SPOT OPEN: {COURSE_NAME}", msg)

                if not notified:
                    notified = True
                    # Keep checking but notify only on transitions
            else:
                if notified:
                    log.info("Class is full again.")
                    notified = False

        except requests.RequestException as e:
            consecutive_failures += 1
            wait = min(CHECK_INTERVAL_SECONDS * (2 ** consecutive_failures), MAX_BACKOFF_SECONDS)
            log.error("Request error: %s. Retrying in %d seconds.", e, wait)
            time.sleep(wait)
            continue
        except KeyboardInterrupt:
            log.info("Stopped by user.")
            break

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
