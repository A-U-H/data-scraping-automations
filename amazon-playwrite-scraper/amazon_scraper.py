import asyncio
import pandas as pd
from playwright.async_api import async_playwright
from datetime import datetime
import random


class AmazonScraper:
    def __init__(self):
        self.data = []
        self.excel_file = "data.xlsx"
        self.max_retries = 3

    async def delay(self, min_time=2, max_time=5):
        """Random delay to mimic human behavior."""
        await asyncio.sleep(random.uniform(min_time, max_time))

    async def start_browser(self):
        """Initialize Playwright browser with stealth."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )
        # Add stealth script to avoid detection
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            window.navigator.chrome = {
                runtime: {},
            };
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
        """)
        self.page = await self.context.new_page()

    async def handle_popups(self):
        """Dismiss various popups that Amazon might show."""
        popup_selectors = [
            "input#attach-close_sideSheet-link",
            "button[aria-label='Close']",
            "button.a-button-close",
            "button[title='Close']",
            "button[data-action='close']",
        ]
        for selector in popup_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    await element.click()
                    await self.delay(1, 2)
            except:
                continue

    async def search_products(self, keyword):
        """Navigate to Amazon and search for the keyword."""
        print("Navigating to Amazon...")
        try:
            await self.page.goto("https://www.amazon.com/", wait_until="commit", timeout=60000)
            await self.delay(3, 5)
            await self.handle_popups()
        except Exception as e:
            print(f"Warning: Could not load homepage: {e}")
            print("Attempting to proceed with search directly...")

        # Locate search bar and enter keyword
        print(f"Searching for: {keyword}")
        try:
            await self.page.wait_for_selector("input#twotabsearchtextbox", timeout=15000)
        except:
            pass

        search_box = await self.page.query_selector("input#twotabsearchtextbox")
        if not search_box:
            search_box = await self.page.query_selector("input[name='field-keywords']")

        if search_box:
            await search_box.fill(keyword)
            await search_box.press("Enter")
            try:
                await self.page.wait_for_load_state("networkidle", timeout=6000)
            except:
                await self.page.wait_for_load_state("domcontentloaded", timeout=6000)
            await self.delay(3, 5)
            await self.handle_popups()
            return True
        else:
            print("Could not find search box.")
            return False

    async def scroll_to_load_all(self):
        """Scroll using PageDown key to load all lazy-loaded products."""
        print("Starting PageDown scrolling to load all results...")
        
        # Wait for initial results to render
        await self.delay(2, 3)
        
        last_count = 0
        no_new_count = 0
        max_scrolls = 20
        scroll_count = 0

        while scroll_count < max_scrolls:
            # Press PageDown 4-6 times with small delays
            page_downs = random.randint(4, 6)
            for _ in range(page_downs):
                await self.page.keyboard.press("PageDown")
                await self.delay(0.8, 1.5)
            
            # Wait for lazy-loaded content to appear
            await self.delay(2, 3)
            
            # Count visible product cards
            current_count = await self.count_visible_products()
            
            print(f"  Scroll {scroll_count + 1}: {current_count} products visible")
            
            if current_count == last_count:
                no_new_count += 1
                if no_new_count >= 3:
                    print("  No new products for 3 scrolls - finished loading")
                    break
            else:
                no_new_count = 0
                print(f"  Found {current_count - last_count} new products")
            
            last_count = current_count
            scroll_count += 1

        # Final scroll to bottom to ensure everything loaded
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await self.delay(2, 3)
        final_count = await self.count_visible_products()
        print(f"Scrolling complete. Total products loaded: {final_count}")

    async def count_visible_products(self):
        """Count product cards currently visible/loaded in DOM."""
        selectors = [
            "div.s-result-item",
            "div[data-component-type='s-search-result']",
            "div[data-asin]",
        ]
        max_count = 0
        for sel in selectors:
            elements = await self.page.query_selector_all(sel)
            max_count = max(max_count, len(elements))
        return max_count

    async def extract_product_links_from_current_page(self):
        """Extract product links from the currently loaded search results page."""
        print("Extracting product links from current page...")
        
        product_links = []
        selectors = [
            "a.a-link-normal.s-no-outline[href*='/dp/']",
            "h2 a.a-link-normal[href*='/dp/']",
            "div.s-result-item h2 a[href*='/dp/']",
            "div[data-component-type='s-search-result'] a[href*='/dp/']",
            "div.s-result-item a[href*='/dp/']",
            "a[href*='/dp/']",
        ]

        for selector in selectors:
            try:
                links = await self.page.query_selector_all(selector)
                if links:
                    for link in links:
                        href = await link.get_attribute("href")
                        if href:
                            clean_url = href.split("?")[0] if "?" in href else href
                            if "/dp/" in clean_url or "/gp/" in clean_url:
                                full_url = f"https://www.amazon.com{clean_url}" if clean_url.startswith("/") else clean_url
                                if full_url not in product_links:
                                    product_links.append(full_url)
                    if product_links:
                        break
            except Exception as e:
                continue

        # Deduplicate while preserving order
        seen = set()
        unique_links = []
        for link in product_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)
        
        print(f"  Found {len(unique_links)} unique products on this page")
        return unique_links

    async def go_to_next_page(self):
        """Click the Next button to go to the next search results page."""
        try:
            next_button = await self.page.query_selector("a.s-pagination-next")
            if next_button:
                await next_button.click()
                await self.page.wait_for_load_state("domcontentloaded", timeout=60000)
                await self.delay(3, 5)
                await self.handle_popups()
                return True
            else:
                print("  No 'Next' button found - reached last page")
                return False
        except Exception as e:
            print(f"  Error navigating to next page: {e}")
            return False

    async def retry_action(self, action, *args, **kwargs):
        """Retry an action with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                return await action(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                await self.delay(attempt * 2, attempt * 3)

    async def scrape_product_details(self, url, index):
        """Scrape details from a single product page with retry logic."""
        print(f"Scraping product {index}: {url[:60]}...")

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await self.delay(3, 5)
            await self.handle_popups()

            # Verify page loaded
            try:
                await self.page.wait_for_selector("body", timeout=10000)
            except:
                print("  Warning: Body not found, but continuing...")

            # Extract product URL
            product_url = self.page.url

            # Extract brand name - multiple strategies
            brand = "Not Found"
            brand_selectors = [
                "a#bylineInfo[href*='brand']",
                "a#bylineInfo[href*='brand'] span",
                "#bylineInfo",
                "span.a-size-base.a-color-secondary:has-text('Brand') + span.a-size-base",
                "tr.po-brand td:has-text('Brand') + td span",
                "#brand",
            ]
            for selector in brand_selectors:
                try:
                    brand_elem = await self.page.query_selector(selector)
                    if brand_elem:
                        brand_text = await brand_elem.text_content()
                        if brand_text:
                            brand_text = brand_text.strip()
                            # Clean up common prefixes
                            brand_text = brand_text.replace("Visit the", "").replace("Store", "").strip()
                            if brand_text and brand_text not in ["", "Brand", "Brand:"]:
                                brand = brand_text
                                break
                except:
                    continue

            # Extract rating (e.g., 4.0 out of 5 stars)
            rating = "Not Found"
            rating_selectors = [
                "span.a-icon-alt",  # Contains "4.0 out of 5 stars"
                "i.a-icon-star span.a-icon-alt",
                "[data-hook='rating-out-of-text']",
                "span[data-hook='rating-out-of-text']",
            ]
            for selector in rating_selectors:
                try:
                    rating_elem = await self.page.query_selector(selector)
                    if rating_elem:
                        rating_text = await rating_elem.text_content()
                        if rating_text and "out of" in rating_text:
                            # Extract just the numeric rating (e.g., "4.0")
                            rating = rating_text.split("out of")[0].strip()
                            break
                        elif rating_text:
                            rating = rating_text.strip()
                            break
                except:
                    continue

            # Extract reviews count (e.g., 5,556 ratings)
            reviews_count = "Not Found"
            reviews_selectors = [
                "span#acrCustomerReviewText",
                "span.a-size-base.a-color-secondary:has-text('ratings')",
                "span[data-hook='total-review-count']",
                "#averageCustomerReviews span",
            ]
            for selector in reviews_selectors:
                try:
                    reviews_elem = await self.page.query_selector(selector)
                    if reviews_elem:
                        reviews_text = await reviews_elem.text_content()
                        if reviews_text and ("ratings" in reviews_text.lower() or "reviews" in reviews_text.lower() or "," in reviews_text):
                            reviews_count = reviews_text.strip()
                            break
                except:
                    continue

            # Extract "bought in past month" data
            bought_last_month = "Not Found"
            bought_selectors = [
                "span:has-text('bought in past month')",
                "span:has-text('bought in the past month')",
                "#socialProofingAsinFaceout span[data-hook='bought-in-last-month']",
                "span[data-hook='bought-in-last-month']",
            ]
            for selector in bought_selectors:
                try:
                    bought_elems = await self.page.query_selector_all(selector)
                    if bought_elems:
                        for bought_elem in bought_elems:
                            bought_text = await bought_elem.text_content()
                            if bought_text and "bought" in bought_text.lower():
                                bought_last_month = bought_text.strip()
                                break
                        if bought_last_month != "Not Found":
                            break
                except:
                    continue

            # Save data
            product_data = {
                "S.No": index,
                "Product URL": product_url,
                "Brand": brand,
                "Rating": rating,
                "Reviews Count": reviews_count,
                "Bought Last Month": bought_last_month,
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            self.data.append(product_data)
            print(f"  [*] Brand: {brand}")
            print(f"  [*] Rating: {rating}")
            print(f"  [*] Reviews Count: {reviews_count}")
            print(f"  [*] Bought: {bought_last_month}")

            # Save to Excel after each product
            self.save_to_excel()

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            import traceback
            traceback.print_exc()

    def save_to_excel(self):
        """Save collected data to Excel file."""
        if self.data:
            df = pd.DataFrame(self.data)
            df.to_excel(self.excel_file, index=False)
            print(f"Data saved to {self.excel_file} ({len(self.data)} products)")

    async def close(self):
        """Close browser and playwright."""
        try:
            await self.browser.close()
        except:
            pass
        try:
            await self.playwright.stop()
        except:
            pass


async def main():
    """Main function to run the scraper."""
    scraper = AmazonScraper()

    try:
        await scraper.start_browser()

        # Get keyword from user
        keyword = input("Enter search keyword for Amazon: ").strip()
        if not keyword:
            print("No keyword entered. Exiting.")
            return

        # Search for products
        success = await scraper.search_products(keyword)
        if not success:
            print("Failed to search. Exiting.")
            return

        # Ask user how many pages to scrape
        try:
            max_pages = int(input("How many pages to scrape? (1-10, recommended 1-3): "))
            max_pages = max(1, min(max_pages, 10))
        except:
            max_pages = 1
            print("Using default: 1 page")

        # Ask how many products per page (optional)
        try:
            max_per_page = int(input("Max products per page? (default 20): "))
            max_per_page = max(1, min(max_per_page, 50))
        except:
            max_per_page = 20

        # Scrape across multiple pages
        all_product_links = []
        current_page = 1

        while current_page <= max_pages:
            print(f"\n{'='*50}")
            print(f"PAGE {current_page} of {max_pages}")
            print(f"{'='*50}")
            
            # Wait 3 seconds then start scrolling
            print("Waiting 3 seconds before scrolling...")
            await asyncio.sleep(3)
            
            # Scroll to load all products on current page
            await scraper.scroll_to_load_all()
            
            # Extract links from current page
            page_links = await scraper.extract_product_links_from_current_page()
            
            if not page_links:
                print(f"No products found on page {current_page}")
                break
            
            # Limit products per page
            page_links = page_links[:max_per_page]
            all_product_links.extend(page_links)
            
            print(f"Page {current_page}: {len(page_links)} products added")
            print(f"Total collected so far: {len(all_product_links)}")
            
            current_page += 1
            
            # Go to next page if we haven't reached the limit
            if current_page <= max_pages:
                print("Navigating to next page...")
                if not await scraper.go_to_next_page():
                    print("Could not navigate to next page. Stopping.")
                    break
            else:
                break

        print(f"\n{'='*50}")
        print(f"TOTAL PRODUCTS FOUND: {len(all_product_links)}")
        print(f"{'='*50}")

        if not all_product_links:
            print("No products to scrape. Exiting.")
            return

        # Ask how many products to actually scrape (from all collected)
        try:
            max_products = int(input(f"How many products to scrape? (1-{len(all_product_links)}): "))
            max_products = min(max_products, len(all_product_links))
        except:
            max_products = min(10, len(all_product_links))
            print(f"Using default: {max_products} products")

        # Scrape each product
        for i, link in enumerate(all_product_links[:max_products], 1):
            await scraper.scrape_product_details(link, i)
            await scraper.delay(2, 4)  # Delay between product visits

        print(f"\n[*] Scraping complete! Data saved to {scraper.excel_file}")
        print(f"Total products scraped: {len(scraper.data)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
