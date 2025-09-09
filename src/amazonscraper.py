# scraper.py
import time
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
try:
    # urllib3 >=1.26 style import
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    from requests.packages.urllib3.util.retry import Retry  # fallback
from bs4 import BeautifulSoup
import pandas as pd

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "en-US, en;q=0.5",
    "Referer": "https://www.amazon.in/",
}

def build_session(headers: Optional[dict] = None) -> requests.Session:
    s = requests.Session()
    s.headers.update(headers or DEFAULT_HEADERS)
    # Configure retries with backoff and Retry-After
    retry_kwargs = dict(
        total=3,
        backoff_factor=1.0,  # 1, 2, 4 seconds
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
    )
    try:
        retry = Retry(**retry_kwargs, respect_retry_after_header=True)
    except TypeError:
        retry = Retry(**retry_kwargs)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

def _extract_title(container: BeautifulSoup) -> Optional[str]:
    # Primary: your original path
    t = None
    title_div = container.find("div", {"data-cy": "title-recipe"})
    if title_div:
        a = title_div.find("a")
        if a:
            h2 = a.find("h2")
            if h2:
                span = h2.find("span")
                if span and span.text:
                    t = span.text.strip()
    # Fallback: generic h2 > a > span
    if not t:
        span = container.select_one("h2 a span")
        if span and span.text:
            t = span.text.strip()
    # Last resort: any h2 text
    if not t:
        h2 = container.find("h2")
        if h2 and h2.text:
            t = h2.get_text(strip=True)
    return t

def scrape_page(url: str, session: Optional[requests.Session] = None) -> Optional[pd.DataFrame]:
    s = session or build_session()
    try:
        # Use explicit timeouts (connect, read)
        resp = s.get(url, timeout=(10, 30))
    except Exception as e:
        print(f"Request error for {url}: {e}")
        return None

    if resp.status_code != 200:
        print(f"Skipping {url} due to status code: {resp.status_code}")
        # If the server told us when to retry, wait politely once
        ra = resp.headers.get("Retry-After")
        if ra and ra.isdigit():
            wait = max(1, int(ra))
            print(f"Retry-After header present; sleeping {wait}s before continuing batch")
            time.sleep(wait)
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    titles, prices, ratings, review_counts, sources = [], [], [], [], []

    product_containers = soup.find_all(
        "div", attrs={"data-asin": True, "data-component-type": "s-search-result"}
    )

    for c in product_containers:
        # Title with fallbacks
        title = _extract_title(c)
        titles.append(title if title else None)

        # Price: prefer a-price-whole, fallback to offscreen
        price = None
        p1 = c.find("span", class_="a-price-whole")
        if p1 and p1.text:
            price = p1.text.strip()
        if not price:
            p2 = c.select_one(".a-price .a-offscreen")
            if p2 and p2.text:
                price = p2.text.strip()
        prices.append(price if price else None)

        # Rating (e.g., "4.2 out of 5 stars")
        rating = None
        r1 = c.find("span", class_="a-icon-alt")
        if r1 and r1.text:
            rating = r1.text.strip()
        ratings.append(rating if rating else None)
        rc = None
        rc1 = c.find("span", class_="a-size-base s-underline-text")
        if rc1 and rc1.text:
            rc = rc1.text.strip()
        reviews = rc if rc else None
        review_counts.append(reviews)
        sources.append(url)

    if not titles and not prices and not ratings and not review_counts:
        return None

    df = pd.DataFrame(
        {
            "Title": titles,
            "Price (₹)": prices,
            "Rating": ratings,
            "Review Count": review_counts,
            "source_url": sources,
        }
    )
    return df
