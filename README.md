# PriceSage

**PriceSage** is a Python-based price comparison and tracking tool that scrapes **Amazon India** and **Flipkart** for product prices. It fetches product details such as **title**, **price**, **rating**, and **review count**, compares them, and identifies the **best deal**.  

With automation, PriceSage can **run multiple times a day**, updating the CSV only with products whose prices have changed, making it a **daily price tracker**.

---

## Features

- Scrapes product data from **Amazon** and **Flipkart**.  
- Extracts **product title**, **price**, **rating**, and **review count**.  
- Compares prices and identifies the **best deal** for each product.  
- Saves a **CSV file** with all products and their latest prices.  
- Can **run multiple times a day** and only updates **changed prices**.  
- **Notifications** on price drops via email or messaging.  
- Modular and extendable — easy to add more e-commerce sites.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/SaiTejesh09/PriceSage.git
cd PriceSage
