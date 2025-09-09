# runscraper.py
import sys
import time
import random
from datetime import datetime
from pathlib import Path
import pandas as pd

# Import from the actual file name 'amazonscraper.py'
from amazonscraper import scrape_page, build_session  # change back to 'scraper' if you rename the file

BASE_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = BASE_DIR / "config.txt"
OUTPUT_FILE = BASE_DIR / "amazon_scraped_data.csv"
APPEND = True

def read_urls(path: Path):
    if not path.exists():
        print(f"URL file not found: {path}")
        return []
    text = path.read_text(encoding="utf-8")
    return [u.strip() for u in text.replace(",", " ").split() if u.strip()]

def save_frame(df: pd.DataFrame, path: Path, append: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    if append and path.exists():
        df.to_csv(path, mode="a", index=False, header=False)
    else:
        df.to_csv(path, index=False, header=True)

def main():
    print(f"[startup] Base dir: {BASE_DIR}")
    print(f"[startup] Config:   {CONFIG_FILE}")
    print(f"[startup] Output:   {OUTPUT_FILE}")

    urls_to_scrape = read_urls(CONFIG_FILE)
    if not urls_to_scrape:
        print("No URLs to scrape. Exiting.")
        return

    session = build_session()
    run_time = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    print(f"Starting scrape at {run_time} for {len(urls_to_scrape)} URL(s)")

    all_frames = []
    for url in urls_to_scrape:
        print(f"Scraping: {url}")
        try:
            df = scrape_page(url, session=session)
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            df = None
        if df is not None and not df.empty:
            df.insert(0, "scrape_time", run_time)
            all_frames.append(df)
        time.sleep(random.uniform(3, 7))

    if all_frames:
        final_df = pd.concat(all_frames, ignore_index=True)
        print(f"Rows this run: {len(final_df)}")
        print(final_df.head())
        save_frame(final_df, OUTPUT_FILE, append=APPEND)
        print(f"Saved to {OUTPUT_FILE} (append={APPEND})")
    else:
        print("No data was scraped.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)
