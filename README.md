# PriceSage

PriceSage is a Python project that monitors Amazon product pages, records prices in a local SQLite database, and sends email alerts whenever the cost goes up or down. The scheduler runs six scraping cycles every day (configurable) and keeps a complete history so you can analyse trends or export clean reports. A built-in sign-up and sign-in flow asks for your email, password, SMTP details, and product URLs so non-technical users can get started without editing JSON files.

---

## Highlights

- Guided sign-up/sign-in that stores the account email and password (hashed with bcrypt) and lets the user enter product URLs interactively.
- Six automated scraping runs per day by default (APScheduler with cron or interval triggers).
- Email notifications for both price drops and increases, with per-product controls.
- SQLite persistence with full price history and summary statistics.
- Command-line tools for one-off scrapes, scheduled runs, and data exports.
- Clean CSV export of the latest insights for further analysis.

---

## Getting Started

1. **Python environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate           # Windows
   # source .venv/bin/activate      # Linux/macOS
   pip install -r requirements.txt
   ```

2. **Configuration**
   - Copy `config.example.json` to `config.json`.
   - Adjust only the scheduling or notification thresholds if you need to; product URLs and email credentials are captured interactively at runtime.

3. **First run (creates your account)**
   ```bash
   python src/main.py --run-once
   ```
   - Choose "sign up" when prompted, then enter:
     1. The email and password you want to use for PriceSage (stored hashed in the database).
     2. The email address that should receive alerts and the SMTP settings that send those alerts (use an app password when using Gmail).
     3. One or more Amazon product URLs to track.
   - The script performs one scrape immediately so you can validate the setup.

4. **Start the scheduler**
   ```bash
   python src/main.py
   ```
   Keep the process running; it will execute six jobs a day (or the schedule you define) and send alerts when prices change.

---

## Configuration Reference (`config.json`)

```json
{
  "scheduler": {
    "runs_per_day": 6,
    "times": ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"],
    "timezone": "Asia/Kolkata",
    "immediate_run": true
  },
  "notifications": {
    "price_change_threshold": 0.0,
    "only_price_drop": false
  },
  "storage": {
    "database_path": "data/prices.db"
  }
}
```

Key notes:
- Provide actual product detail URLs during the interactive prompts to get accurate data (search result pages are less reliable).
- `times` overrides `runs_per_day`. Remove `times` to let the app space runs evenly by interval.
- `price_change_threshold` lets you ignore tiny changes (set to `5` to suppress alerts under ₹5, for example).
- Credentials and product lists are stored in the local SQLite database (`data/prices.db`). Passwords are hashed with bcrypt; SMTP app passwords are stored as-is so that emails can be sent automatically.

---

## Command-Line Tools

- `python src/main.py --run-once`  
  Single scrape after you log in. Ideal for quick checks or manual updates.

- `python src/main.py --report-minutes 720`  
  Show price changes recorded in the last 12 hours (prompts for login, but does not scrape).

- `python src/runscraper.py [optional-config-path]`  
  Convenience wrapper that always performs one run (identical to `--run-once`).

- `python src/preprocessdata.py`  
  Export a CSV summary (`src/reports/price_summary.csv`) with min, max, average, and the latest price per product.

All commands accept `--config path/to/settings.json` if you maintain multiple profiles.

---

## Project Structure

- `src/auth.py` - prompts for sign-up/sign-in, hashes passwords, and stores SMTP settings.
- `src/amazonscraper.py` - resilient Amazon product fetcher with retry logic.
- `src/storage.py` - SQLite persistence layer for users, products, and price history.
- `src/tracker.py` - orchestrates scraping, change detection, and notifications.
- `src/notifier.py` - SMTP email notification service.
- `src/main.py` - interactive CLI entry point with scheduler integration.
- `src/preprocessdata.py` - generates analytical CSV summaries from the database.
- `config.json` - scheduler and notification defaults (copy from the example template).
- `data/prices.db` - generated SQLite database containing accounts, tracked products, and history.

---

## Suggested Enhancements

1. Add support for additional retailers or scraping APIs.
2. Integrate a small Streamlit dashboard for visualising price trends.
3. Deploy as a container and run on a cheap VPS or home server.
4. Extend notifications with Slack or Telegram webhooks.

---

## Disclaimer

Scraping may violate a website's terms of service. Use PriceSage responsibly, respect Amazon's robots policies, and consider adding longer delays or official APIs when scaling beyond personal use.
