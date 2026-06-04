# Google Maps Scraper

A Python script that scrapes business data from Google Maps and saves it to an Excel file.

## Features

- Search for businesses on Google Maps using any keyword
- Automatically scrolls to load multiple pages of results
- Visits each business listing to extract:
  - Business name
  - Rating
  - Address
  - Phone number
  - Opening hours
  - Website URL
  - Business logo/image URL
- Saves all data to `data.xlsx`

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the script:
```bash
python google_maps_scraper.py
```

Enter your search keyword when prompted (e.g., "software companies in bangalore", "restaurants in new york", etc.)

The script will:
1. Open Chrome browser
2. Search Google Maps
3. Scroll through results
4. Visit each business listing
5. Extract information
6. Save to `data.xlsx`

### Save to Google Sheets

1. Enable Google Sheets API and download `credentials.json` from Google Cloud Console
2. Place `credentials.json` in the project folder
3. Run with `--gsheet` flag:
```bash
python google_maps_scraper.py "software companies bangalore" --gsheet "My Results"
```

Options:
- `--gsheet <name>` - Save to Google Sheets instead of Excel
- `--creds <file>` - Path to Google credentials JSON (default: credentials.json)

## Output

The Excel file contains the following columns:
- `name` - Business name
- `rating` - Google Maps rating
- `address` - Physical address
- `phone` - Contact phone number
- `opening_hours` - Operating hours
- `website` - Official website URL
- `image_url` - Business logo/image URL

## Notes

- The script uses Chrome browser (will download ChromeDriver automatically)
- Set `headless=True` in the `GoogleMapsScraper` constructor for headless mode
- Adjust `scroll_count` parameter to load more/fewer results
- Google may block automated requests; use responsibly and add delays if needed

## Disclaimer

This script is for educational purposes. Respect Google's Terms of Service and rate limits when scraping. Consider using the official Google Maps API for production use.
