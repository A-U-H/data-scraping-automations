"""
Google Maps Scraper using Playwright with Stealth
Extracts business information and saves to Excel

Requirements:
    pip install playwright pandas playwright-stealth openpyxl
    playwright install chromium
"""

import asyncio
import pandas as pd
import random
import time
import sys
from pathlib import Path
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
from playwright_stealth import Stealth
import json


class GoogleMapsScraper:
    def __init__(self, headless: bool = False):
        """Initialize the scraper with Playwright"""
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context = None
        self.page: Optional[Page] = None
        self.results: List[Dict] = []
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        ]

    async def start(self):
        """Launch browser with stealth settings"""
        playwright = await async_playwright().start()

        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create context with random user agent
        user_agent = random.choice(self.user_agents)
        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080},
            locale='en-US'
        )

        self.page = await self.context.new_page()

        # Apply stealth to avoid detection
        stealth = Stealth()
        await stealth.apply_stealth_async(self.page)

    async def handle_popups(self):
        """Handle cookie consent and other pop-ups"""
        try:
            # Accept cookies if shown
            accept_button = await self.page.wait_for_selector(
                "button:has-text('Accept all'), button:has-text('I agree'), button:has-text('Accept')",
                timeout=3000
            )
            if accept_button:
                await accept_button.click()
                await self.page.wait_for_timeout(1000)
        except:
            pass

    async def search(self, keyword: str):
        """Perform search on Google Maps"""
        print(f"Searching for: {keyword}")

        # Encode keyword for URL
        from urllib.parse import quote
        encoded_query = quote(keyword.replace(' ', '+'))

        # Go directly to search URL
        search_url = f"https://www.google.com/maps/search/{encoded_query}"

        try:
            await self.page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
            await self.page.wait_for_timeout(5000)
        except Exception as e:
            print(f"Navigation error: {e}")
            # Try with simpler approach
            await self.page.goto("https://www.google.com/maps", wait_until='domcontentloaded', timeout=60000)
            await self.page.wait_for_timeout(3000)

            # Find search box and type
            try:
                search_box = await self.page.wait_for_selector("input#searchboxinput", timeout=10000)
                if search_box:
                    await search_box.fill(keyword)
                    await self.page.keyboard.press("Enter")
                    await self.page.wait_for_timeout(5000)
            except Exception as e2:
                print(f"Failed to search: {e2}")
                return False

        # Handle any popups
        await self.handle_popups()
        return True

    async def scroll_feed(self, max_scrolls: int = 30):
        """Scroll the results feed to load all listings"""
        print("Scrolling to load all results...")

        last_height = 0
        no_change_count = 0

        for i in range(max_scrolls):
            try:
                # Wait for feed to be present
                feed = await self.page.wait_for_selector("div[role='feed']", timeout=5000)
                if not feed:
                    print("Feed container not found")
                    break

                # Get current number of results
                current_results = await self.page.query_selector_all("div[role='article']")
                current_count = len(current_results)

                # Scroll the feed
                await self.page.evaluate("""
                    const feed = document.querySelector("div[role='feed']");
                    if (feed) {
                        feed.scrollTop = feed.scrollHeight;
                    }
                """)

                await self.page.wait_for_timeout(2000)

                # Check if new results loaded
                new_results = await self.page.query_selector_all("div[role='article']")
                new_count = len(new_results)

                print(f"Scroll {i+1}: {new_count} listings loaded")

                if new_count == current_count:
                    no_change_count += 1
                    if no_change_count >= 3:
                        print(f"Reached end of results after {i+1} scrolls. Total: {new_count} listings")
                        break
                else:
                    no_change_count = 0
                    last_height = new_count

            except Exception as e:
                print(f"Scroll error at iteration {i+1}: {e}")
                # If we've already loaded some results, continue
                if i > 0:
                    break
                else:
                    await self.page.wait_for_timeout(2000)

    async def extract_all_listing_links(self) -> List[str]:
        """Extract links to all business listings from the results page"""
        links = []

        try:
            # Find all result articles
            articles = await self.page.query_selector_all("div[role='article']")

            for article in articles:
                try:
                    link_element = await article.query_selector("a")
                    if link_element:
                        href = await link_element.get_attribute("href")
                        if href and "/maps/place/" in href:
                            links.append(href)
                except:
                    continue

        except Exception as e:
            print(f"Error extracting links: {e}")

        print(f"Found {len(links)} business links")
        return list(set(links))  # Remove duplicates

    async def extract_business_details(self, url: str) -> Optional[Dict]:
        """Navigate to business page and extract all details"""
        try:
            # Open business page
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self.page.wait_for_timeout(3000)

            details = {
                'name': '',
                'rating': '',
                'address': '',
                'website': '',
                'phone': '',
                'reviews': ''
            }

            # Extract name (usually h1)
            try:
                name_selectors = [
                    "h1",
                    "h1[class*='header']",
                    "div[role='heading']",
                    "[data-attrid='title']",
                ]
                for selector in name_selectors:
                    name_el = await self.page.query_selector(selector)
                    if name_el:
                        name_text = await name_el.inner_text()
                        if name_text and len(name_text.strip()) > 0:
                            details['name'] = name_text.strip()
                            break
            except:
                pass

            # Extract rating (aria-label with stars)
            try:
                rating_el = await self.page.query_selector("span[aria-label*='stars']")
                if rating_el:
                    aria_label = await rating_el.get_attribute("aria-label")
                    if aria_label:
                        import re
                        match = re.search(r'(\d+\.?\d*)', aria_label)
                        if match:
                            details['rating'] = match.group(1)
            except:
                pass

            # Extract address
            try:
                address_selectors = [
                    "button[data-item-id='address']",
                    "button[aria-label*='address']",
                    "[data-attrid='address']",
                    "div[data-item-id*='address']",
                ]
                for selector in address_selectors:
                    addr_el = await self.page.query_selector(selector)
                    if addr_el:
                        addr_text = await addr_el.inner_text()
                        if addr_text and len(addr_text.strip()) > 5:
                            # Clean up control characters and whitespace
                            import re
                            addr_clean = re.sub(r'[\u0000-\u001F\ufeff]+', ' ', addr_text).strip()
                            addr_clean = re.sub(r'\s+', ' ', addr_clean).strip()
                            details['address'] = addr_clean
                            break
            except:
                pass

            # Extract reviews
            try:
                review_selectors = [
                    "button[aria-label*='reviews']",
                    "span[aria-label*='reviews']",
                    "[data-attrid='reviews']",
                    "div[jsaction*='reviews']",
                ]
                for selector in review_selectors:
                    review_el = await self.page.query_selector(selector)
                    if review_el:
                        aria_label = await review_el.get_attribute("aria-label")
                        if aria_label:
                            import re
                            match = re.search(r'[\d,]+', aria_label)
                            if match:
                                details['reviews'] = match.group(0)
                                break
                        text = await review_el.inner_text()
                        if text:
                            import re
                            match = re.search(r'[\d,]+', text)
                            if match:
                                details['reviews'] = match.group(0)
                                break
            except:
                pass

            # Extract website
            try:
                website_selectors = [
                    "button[data-item-id='authority']",
                    "a[data-item-id='authority']",
                    "a[href*='http']:not([href*='google'])",
                    "button[aria-label*='website']",
                    "a[data-attrid='authority']",
                ]
                for selector in website_selectors:
                    website_el = await self.page.query_selector(selector)
                    if website_el:
                        # Try href first
                        website_href = await website_el.get_attribute("href")
                        if website_href and 'google' not in website_href:
                            details['website'] = website_href
                            break
                        # Try data-url
                        data_url = await website_el.get_attribute("data-url")
                        if data_url and 'google' not in data_url:
                            details['website'] = data_url
                            break
            except:
                pass

            # Extract phone number
            try:
                # Look for tel: links first
                tel_link = await self.page.query_selector("a[href^='tel:']")
                if tel_link:
                    href = await tel_link.get_attribute("href")
                    if href:
                        phone = href.replace("tel:", "").strip()
                        # Keep digits, spaces, dashes, parentheses only
                        import re
                        phone = re.sub(r'[^\d\s\-\(\)]', '', phone).strip()
                        if phone:
                            details['phone'] = phone
                else:
                    # Look for phone button with data
                    phone_el = await self.page.query_selector("button[data-item-id*='phone'], button[aria-label*='phone']")
                    if phone_el:
                        phone_text = await phone_el.inner_text()
                        if phone_text:
                            import re
                            phone_match = re.search(r'(\+?[\d\s\-\(\)]{7,})', phone_text)
                            if phone_match:
                                details['phone'] = phone_match.group(1).strip()
            except:
                pass

            return details

        except Exception as e:
            print(f"Error extracting details from {url}: {e}")
            return None

    async def scrape_all(self, keyword: str, max_listings: int = None, max_scrolls: int = 30):
        """Main scraping workflow"""
        try:
            # Start browser
            print("Starting browser...")
            await self.start()
            print("Browser started")

            # Perform search
            print("Starting search...")
            search_success = await self.search(keyword)
            if not search_success:
                print("Search failed")
                return False
            print("Search completed")

            # Scroll to load all results
            print("Starting scroll...")
            await self.scroll_feed(max_scrolls)
            print("Scrolling completed")

            # Get all business links
            print("Extracting links...")
            links = await self.extract_all_listing_links()
            print(f"Found {len(links)} businesses to scrape")

            if not links:
                print("No businesses found.")
                return True

            # Limit links if max_listings specified
            if max_listings is not None:
                links = links[:max_listings]
                print(f"Limited to first {len(links)} listings")

            # Visit each business and extract details
            for idx, link in enumerate(links, 1):
                print(f"Scraping {idx}/{len(links)}: {link}")

                details = await self.extract_business_details(link)
                if details:
                    self.results.append(details)

                # Small delay to avoid rate limiting
                await asyncio.sleep(random.uniform(1, 2))

            print("All details extracted")
            return True

        except Exception as e:
            print(f"Scraping error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if self.browser:
                await self.browser.close()

    def save_to_excel(self, filename: str = 'data.xlsx'):
        """Save results to Excel file"""
        if not self.results:
            print("No data to save")
            return

        df = pd.DataFrame(self.results)

        # Reorder columns
        column_order = ['name', 'rating', 'address', 'phone', 'website', 'reviews']
        available_columns = [col for col in column_order if col in df.columns]
        df = df[available_columns]

        # Remove duplicates
        df = df.drop_duplicates(subset=['name', 'address'], keep='first')

        # Save
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"\nSaved {len(df)} records to '{filename}'")

    def save_to_google_sheets(self, spreadsheet_name: str, credentials_file: str = 'credentials.json'):
        """Save results to Google Sheets"""
        import gspread
        from google.oauth2.service_account import Credentials

        if not self.results:
            print("No data to save")
            return

        df = pd.DataFrame(self.results)
        column_order = ['name', 'rating', 'address', 'phone', 'website', 'reviews']
        available_columns = [col for col in column_order if col in df.columns]
        df = df[available_columns]
        df = df.drop_duplicates(subset=['name', 'address'], keep='first')

        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
            client = gspread.authorize(creds)

            try:
                sheet = client.open(spreadsheet_name).sheet1
            except gspread.SpreadsheetNotFound:
                sheet = client.create(spreadsheet_name).sheet1

            sheet.clear()
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            print(f"\nSaved {len(df)} records to Google Sheet '{spreadsheet_name}'")
        except Exception as e:
            print(f"Error saving to Google Sheets: {e}")


async def main():
    """Entry point"""
    print("=" * 60)
    print("GOOGLE MAPS SCRAPER (Playwright)")
    print("=" * 60)

    # Show usage if needed
    if len(sys.argv) > 0 and '-h' in sys.argv or '--help' in sys.argv:
        print("\nUsage:")
        print("  python google_maps_scraper.py <keyword> [max_listings]")
        print("  python google_maps_scraper.py \"software companies new york\" 10")
        print("  python google_maps_scraper.py \"software companies new york\" all")
        print("\nOptions:")
        print("  --gsheet <name>   Save to Google Sheets instead of Excel")
        print("  --creds <file>    Path to Google credentials JSON (default: credentials.json)")
        print("\nParameters:")
        print("  keyword        - Search term (required)")
        print("  max_listings   - Number of listings to scrape (optional, default: all)")
        print("                   Use 'all' or 0 to scrape all available listings")
        print("\nExamples:")
        print("  python google_maps_scraper.py \"software companies bangalore\"")
        print("  python google_maps_scraper.py \"restaurants london\" 20")
        print("  python google_maps_scraper.py \"hotels paris\" all")
        return

    # Get keyword and listing count from command line or prompt
    if len(sys.argv) > 2:
        keyword = " ".join(sys.argv[1:-1])
        max_listings_arg = sys.argv[-1]
    elif len(sys.argv) > 1:
        # If only 1 arg, it's the keyword, default to all
        keyword = " ".join(sys.argv[1:])
        max_listings_arg = "all"
    else:
        keyword = input("Enter search keyword (e.g., 'software companies in bangalore'): ").strip()
        max_listings_arg = input("How many listings to scrape? (number or 'all'): ").strip().lower()

    if not keyword:
        print("No keyword provided. Exiting.")
        return

# Parse max listings
    if max_listings_arg.lower() in ['all', '0', '']:
        max_listings = None  # No limit
    else:
        try:
            max_listings = int(max_listings_arg)
            if max_listings <= 0:
                print("Invalid number. Using default (all).")
                max_listings = None
        except ValueError:
            print("Invalid input. Using default (all).")
            max_listings = None

    scraper = GoogleMapsScraper(headless=False)

    gsheet_spreadsheet = None
    creds_file = 'credentials.json'
    for i, arg in enumerate(sys.argv):
        if arg == '--gsheet' and i + 1 < len(sys.argv):
            gsheet_spreadsheet = sys.argv[i + 1]
        elif arg == '--creds' and i + 1 < len(sys.argv):
            creds_file = sys.argv[i + 1]

    try:
        success = await scraper.scrape_all(keyword, max_listings=max_listings, max_scrolls=30)
        if success:
            if gsheet_spreadsheet:
                scraper.save_to_google_sheets(gsheet_spreadsheet, creds_file)
            else:
                scraper.save_to_excel('data.xlsx')
            print(f"\nScraping complete! Total records: {len(scraper.results)}")
    except KeyboardInterrupt:
        print("\nScraping interrupted")
        scraper.save_to_excel('data.xlsx')
    except Exception as e:
        print(f"Error: {e}")
        scraper.save_to_excel('data.xlsx')


if __name__ == "__main__":
    asyncio.run(main())
