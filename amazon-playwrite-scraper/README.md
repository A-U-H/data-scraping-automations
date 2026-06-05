# Amazon Scraper

A simple Amazon search result scraper built with Playwright, Python, and Pandas.

## What it does

- Opens Amazon.com in a browser
- Searches for a keyword entered by the user
- Scrolls through search results to load product listings
- Extracts product URLs from the search result pages
- Visits individual product pages
- Scrapes brand, rating, review count, and bought-in-past-month information
- Saves the collected data to `data.xlsx`

## Requirements

- Python 3.9+
- See `requirements.txt` for Python package dependencies

## Setup

1. Create and activate a Python virtual environment (recommended).

```powershell
python -m venv venv
.\\venv\\Scripts\\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Install Playwright browsers if needed:

```powershell
python -m playwright install
```

## Usage

Run the scraper:

```powershell
python amazon_scraper.py
```

Follow the prompts:

1. Enter the search keyword
2. Select how many result pages to scrape
3. Select how many products to scrape from the collected links

Data is saved to `data.xlsx` in the project folder.

## Notes

- The scraper uses a non-headless Chromium browser for improved reliability.
- It includes basic stealth techniques and random delays to reduce detection.
- Amazon page layout changes may require selector updates.

## Files

- `amazon_scraper.py` - main scraper script
- `requirements.txt` - dependency list
- `data.xlsx` - output file generated after a successful run
