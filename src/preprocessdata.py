import pandas as pd

def clean_and_sort_data(input_path: str, output_path: str):
    """
    Cleans and sorts scraped Amazon data from a CSV file.

    Args:
        input_path (str): The file path for the raw CSV data.
        output_path (str): The file path to save the cleaned CSV data.
    """
    try:
        df = pd.read_csv(input_path)

        df['Price (₹)'] = df['Price (₹)'].astype(str).str.replace(',', '', regex=False)
        df['Price (₹)'] = pd.to_numeric(df['Price (₹)'], errors='coerce')
        if 'Review Count' in df.columns:
            df['Review Count'] = df['Review Count'].astype(str).str.replace(',', '', regex=False)
            df['Review Count'] = pd.to_numeric(df['Review Count'], errors='coerce')

        df.dropna(subset=['Price (₹)'], inplace=True)

        df_sorted = df.sort_values(
            by=['Price (₹)', 'Review Count'],
            ascending=[True, False],
            na_position='last'
        )

        df_sorted.to_csv(output_path, index=False)
        
        print(f"✅ Success! Data cleaned and saved to {output_path}")
        print("\n--- Top 5 Products After Sorting ---")
        print(df_sorted.head())

    except FileNotFoundError:
        print(f"❌ Error: The file was not found at the path: {input_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    input_file_path = r"C:\Users\kalya\OneDrive\Desktop\sracping\PriceSage\src\amazon_scraped_data.csv"
    output_file_path = r"C:\Users\kalya\OneDrive\Desktop\sracping\PriceSage\src\amazon_scraped_data_cleaned.csv"

    clean_and_sort_data(input_file_path, output_file_path)
