# Dartmouth Course Seat Monitor

A lightweight Python script that monitors the [Dartmouth Timetable](https://oracle-www.dartmouth.edu/dart/groucho/timetable.main) for open seats in a specific course and sends you notifications the moment a spot opens up.

Currently configured for **COSC 031 - Algorithms** (CRN 31322, Spring 2026), but easily adaptable to any course.

## How It Works

1. Every 5 minutes, the script POSTs to the Dartmouth timetable and scrapes the HTML response
2. It finds the target course by CRN and compares current enrollment vs. the class limit
3. When enrollment drops below the limit, it sends:
   - A **macOS desktop notification** (with sound)
   - A **phone push notification** via [ntfy.sh](https://ntfy.sh) (free, no account required)
4. If the server errors out, it backs off exponentially (up to 30 min) to avoid getting rate-limited

## Setup

### Prerequisites

- Python 3.10+
- macOS (for desktop notifications — the ntfy.sh phone alerts work on any OS)

### Install Dependencies

```bash
pip install requests beautifulsoup4
```

### Configure Phone Notifications (Optional)

1. Install the **ntfy** app on your phone ([iOS](https://apps.apple.com/us/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
2. Open the app and subscribe to a unique topic name (e.g. `dartmouth-cosc031-yourname`)
3. Edit `NTFY_TOPIC` on **line 26** of `monitor.py` to match your topic name:
   ```python
   NTFY_TOPIC = "dartmouth-cosc031-yourname"
   ```

### Run

```bash
python3 monitor.py
```

Leave the terminal open. The script logs to both stdout and `monitor.log`.

Press `Ctrl+C` to stop.

## Monitoring a Different Course

Edit the configuration block at the top of `monitor.py`:

```python
TARGET_CRN = "31322"              # CRN from the timetable
COURSE_NAME = "COSC 031 - Algorithms"  # Display name (for notifications)
TERM = "202603"                   # Term code (e.g. 202603 = Spring 2026)
DEPT = "COSC"                     # Department code
```

You can find these values on the [Dartmouth Timetable](https://oracle-www.dartmouth.edu/dart/groucho/timetable.main). Term codes follow the pattern `YYYYMM` where MM is `01` (Winter), `03` (Spring), `06` (Summer), `09` (Fall).

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `TARGET_CRN` | `"31322"` | Course Reference Number to watch |
| `COURSE_NAME` | `"COSC 031 - Algorithms"` | Display name used in notifications |
| `TERM` | `"202603"` | Dartmouth term code |
| `DEPT` | `"COSC"` | Department code |
| `CHECK_INTERVAL_SECONDS` | `300` (5 min) | How often to check |
| `MAX_BACKOFF_SECONDS` | `1800` (30 min) | Max retry delay on errors |
| `NTFY_TOPIC` | `"dartmouth-cosc031-CHANGEME"` | Your ntfy.sh topic name |

## License

MIT
