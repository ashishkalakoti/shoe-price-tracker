import asyncio
import json
from playwright.async_api import async_playwright
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import logging
import traceback
import asyncio

# ---------------------- Logging Setup ----------------------
LOG_FILE = "shoe_scraper.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ---------------------- Config ----------------------
SHOES = [
    "Asics Novablast",
    "Asics Gel-Nimbus",
    "Saucony Kinvara",
    "Saucony Tempus",
    "Saucony Endorphin",
    "Saucony Triumph",
    "Brooks Ghost",
    "Brooks Adrenaline",
    "Brooks Glycerin"
]

EMAIL_FROM = "ashishkalakoti@gmail.com"
EMAIL_TO = "ashishkalakoti@gmail.com"
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")  # Set as secret in GitHub

# ---------------------- Flipkart Scraper ----------------------
async def scrape_flipkart(query):
    results = []
    url = f"https://www.flipkart.com/search?q={query}"
    logger.info(f"Scraping Flipkart for query: {query}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            logger.debug(f"Opening URL: {url}")
            await page.goto(url, timeout=25000)

            content = await page.content()
            start = content.find("window.__PRELOADED_STATE__ = ")
            if start != -1:
                start += len("window.__PRELOADED_STATE__ = ")
                end = content.find("};", start) + 1
                json_text = content[start:end]
                data = json.loads(json_text)
                try:
                    products = data['product']['products']
                    for p in products[:10]:
                        title = p.get('title', 'No title')
                        price = p.get('price', {}).get('value', 'Price not found')
                        url = "https://www.flipkart.com" + p.get('url', '')
                        results.append(f"{title} - ₹{price} - {url}")
                except KeyError:
                    results.append("Could not extract products from JSON")
            await browser.close()
    except Exception as e:
        logger.error(f"Flipkart failed for {query} at {url}: {type(e).__name__} - {e}")
        logger.error(traceback.format_exc())
    logger.info(f"Flipkart results for {query}: {len(results)} items")
    return results

# ---------------------- Myntra Scraper ----------------------
async def scrape_myntra(query):
    results = []
    url = f"https://www.myntra.com/{query.replace(' ', '-')}"
    logger.info(f"Scraping Myntra for query: {query}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            logger.debug(f"Opening URL: {url}")
            await page.goto(url, timeout=25000)

            try:
                script = await page.locator('script[id="__NEXT_DATA__"]').inner_text(timeout=7000)
                data = json.loads(script)
                products = data["props"]["pageProps"]["searchResults"]["products"]
                for p in products[:10]:
                    title = p.get("productName", "No title")
                    price = p.get("price", {}).get("discounted", p.get("price", {}).get("mrp", "Price not found"))
                    link = "https://www.myntra.com" + p.get("landingPageUrl", "")
                    results.append(f"{title} - ₹{price} - {link}")

            except Exception as e_json:
                logger.warning(f"Myntra JSON parse failed for {query}: {e_json}")
                try:
                    await page.wait_for_selector("li.product-base", timeout=15000)
                    items = page.locator("li.product-base")
                    count = min(10, await items.count())
                    for i in range(count):
                        try:
                            brand = await items.nth(i).locator(".product-brand").inner_text(timeout=1000)
                            title = await items.nth(i).locator(".product-product").inner_text(timeout=1000)
                            price = await items.nth(i).locator(".product-price").inner_text(timeout=1000)
                            results.append(f"{brand} {title} - {price}")
                        except:
                            continue
                except Exception as e_html:
                    results.append(f"Myntra failed: {type(e_html).__name__}")
                    logger.error(f"Myntra HTML scrape failed for {query} at {url}: {type(e_html).__name__} - {e_html}")
            await browser.close()
    except Exception as e:
        logger.error(f"Myntra failed for {query} at {url}: {type(e).__name__} - {e}")
        logger.error(traceback.format_exc())
    logger.info(f"Myntra results for {query}: {len(results)} items")
    return results

# ---------------------- Ajio Scraper ----------------------
async def scrape_ajio(query):
    results = []
    url = f"https://www.ajio.com/search/?text={query}"
    logger.info(f"Scraping Ajio for query: {query}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            logger.debug(f"Opening URL: {url}")
            await page.goto(url, timeout=25000)

            content = await page.content()
            start = content.find("window.__INITIAL_STATE__ = ")
            if start != -1:
                start += len("window.__INITIAL_STATE__ = ")
                end = content.find("};", start) + 1
                json_text = content[start:end]
                data = json.loads(json_text)
                try:
                    products = data['search']['products']
                    for p in products[:10]:
                        title = p.get('brand', '') + " " + p.get('name', '')
                        price = p.get('price', {}).get('mrp', 'Price not found')
                        url = "https://www.ajio.com" + p.get('url', '')
                        results.append(f"{title} - ₹{price} - {url}")
                except KeyError:
                    results.append("Could not extract products from JSON")
            await browser.close()
    except Exception as e:
        logger.error(f"Ajio failed for {query} at {url}: {type(e).__name__} - {e}")
        logger.error(traceback.format_exc())
    logger.info(f"Ajio results for {query}: {len(results)} items")
    return results

# ---------------------- Send Email ----------------------
def send_email(subject, content):
    logger.info(f"Preparing to send email: {subject}")
    logger.debug(f"Email content preview: {content[:300]}...")
    message = Mail(
        from_email=EMAIL_FROM,
        to_emails=EMAIL_TO,
        subject=subject,
        plain_text_content=content
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent! Status code: {response.status_code}")
    except Exception as e:
        logger.error("Error sending email: %s", traceback.format_exc())
        if hasattr(e, "body"):
            logger.error("SendGrid response body: %s", e.body)

# ---------------------- Retry Wrapper ----------------------
async def safe_scrape(scraper, name, query):
    for attempt in range(3):
        try:
            return await scraper(query)
        except Exception as e:
            logger.error(f"{name} scrape attempt {attempt+1} failed for {query}: {e}")
            await asyncio.sleep(3)
    return [f"{name} failed after 3 retries."]

# ---------------------- Main ----------------------
async def main():
    all_results = ""
    for shoe in SHOES:
        query = f"{shoe}"
        logger.info(f"Processing {query}")
        all_results += f"\n=== {query} ===\n"

        flipkart = await safe_scrape(scrape_flipkart, "Flipkart", query)
        myntra = await safe_scrape(scrape_myntra, "Myntra", query)
        ajio = await safe_scrape(scrape_ajio, "Ajio", query)

        all_results += "Flipkart:\n" + "\n".join(flipkart) + "\n"
        all_results += "Myntra:\n" + "\n".join(myntra) + "\n"
        all_results += "Ajio:\n" + "\n".join(ajio) + "\n"

    send_email("Daily Shoe Prices", all_results)
    logger.info("Workflow completed successfully.")

# ---------------------- Run ----------------------
if __name__ == "__main__":
    asyncio.run(main())
