import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

HEADERS = ({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US, en;q=0.5',
    'Referer': 'https://www.amazon.in/'
})

def scrape_page(url):
    webpage = requests.get(url, headers=HEADERS)
    if webpage.status_code != 200:
        print(f"Skipping {url} due to status code: {webpage.status_code}")
        return None

    soup = BeautifulSoup(webpage.content, "html.parser")
    
    titles, prices, ratings, review_counts = [], [], [], []
    
    product_containers = soup.find_all("div", attrs={'data-asin': True, 'data-component-type': 's-search-result'})

    for container in product_containers:
        # Title (Using your original selector)
        try:
            title_tag = container.find("div",{"data-cy":"title-recipe"}).find("a").find("h2").find("span")
            title = title_tag.text.strip()
            titles.append(title)
        except AttributeError:
            titles.append(None)
        # Price
        try:
            prices.append(container.find("span", class_="a-price-whole").text.strip())
        except AttributeError:
            prices.append(None)
        # Rating
        try:
            ratings.append(container.find("span", class_="a-icon-alt").text.strip())
        except AttributeError:
            ratings.append(None)
        # Review Count
        try:
            review_counts.append(container.find("span", class_="a-size-base s-underline-text").text.strip())
        except AttributeError:
            review_counts.append(None)

    df = pd.DataFrame({
        'Title': titles, 'Price (₹)': prices, 'Rating': ratings, 'Review Count': review_counts
    })
    # df.dropna(how='all', inplace=True)
    return df

if __name__ == "__main__":
    
    urls_input = input("Please paste the Amazon URLs to scrape (separated by a space or comma):\n")
    
    urls_to_scrape = [url.strip() for url in urls_input.replace(",", " ").split()]

    all_dataframes = []
    
    print(f"\nStarting to scrape {len(urls_to_scrape)} URLs...")

    for url in urls_to_scrape:
        if not url:
            continue
        print(f"Scraping: {url}")
        page_df = scrape_page(url)
        if page_df is not None and not page_df.empty:
            all_dataframes.append(page_df)
        
        time.sleep(2) 
        
    if all_dataframes:
        final_df = pd.concat(all_dataframes, ignore_index=True)
        print("\n--- Scraping Complete ---")
        print(f"Total products scraped: {len(final_df)}")
        print(final_df.head())
        
        output_filename = "amazon_scraped_data.csv"
        final_df.to_csv(output_filename, index=False)
        print(f"\nData successfully saved to {output_filename}")
    else:
        print("No data was scraped.")