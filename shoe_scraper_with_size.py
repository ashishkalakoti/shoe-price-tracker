import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# === CONFIG ===
SHOES = [
    "Asics Novablast", "Asics Gel-nimbus", "Saucony kinvara",
    "Saucony Tempus", "Saucony Endorphin", "Brooks Ghost",
    "Brooks Adrenaline", "Brooks Glycerin", "Hoka Arahi", "Hoka Skyflow"
]

SIZES = ["UK 8", "UK 8.5", "UK 9"]

WEBSITES = {
    "Flipkart": "https://www.flipkart.com/search?q={query}",
    "Myntra": "https://www.myntra.com/{query}",
    "Ajio": "https://www.ajio.com/search/?text={query}",
    "Amazon": "https://www.amazon.in/s?k={query}"
}

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# === SCRAPER FUNCTIONS ===
async def scrape_flipkart(page, shoe, size):
    url = WEBSITES["Flipkart"].format(query=shoe.replace(" ", "+"))
    await page.goto(url)
    await page.wait_for_timeout(2000)
    try:
        first_product = page.locator("a._1fQZEK").first
        await first_product.click()
        await page.wait_for_timeout(2000)
        # Sizes buttons are often in '._23FHuj' or '._2Xfa2_'
        size_button = page.locator(f"button[title='{size}']").first
        await size_button.click(timeout=10000)
        price = await page.locator("._30jeq3._16Jk6d").inner_text(timeout=10000)
        return price
    except PlaywrightTimeoutError:
        return f"Error: Size {size} not found"

async def scrape_myntra(page, shoe, size):
    url = WEBSITES["Myntra"].format(query=shoe.replace(" ", "-").lower())
    await page.goto(url)
    await page.wait_for_timeout(2000)
    try:
        first_product = page.locator("li.product-base").first
        await first_product.click()
        await page.wait_for_timeout(2000)
        # Price selector updated
        price = await page.locator("span.pdp-price").inner_text(timeout=10000)
        return price
    except PlaywrightTimeoutError:
        return f"Error: Price not found for {size}"

async def scrape_ajio(page, shoe, size):
    url = WEBSITES["Ajio"].format(query=shoe.replace(" ", "+"))
    await page.goto(url)
    await page.wait_for_timeout(2000)
    try:
        first_product = page.locator("div.prod-name").first
        await first_product.click()
        await page.wait_for_timeout(2000)
        price = await page.locator("div.prod-sp").inner_text(timeout=10000)
        return price
    except PlaywrightTimeoutError:
        return f"Error: Price not found for {size}"

async def scrape_amazon(page, shoe, size):
    url = WEBSITES["Amazon"].format(query=shoe.replace(" ", "+"))
    await page.goto(url)
    await page.wait_for_timeout(2000)
    try:
        first_product = page.locator("div.s-main-slot div[data-component-type='s-search-result']").first
        await first_product.click()
        await page.wait_for_timeout(2000)
        # Size selection may vary, try approximate match
        price = await page.locator("#priceblock_ourprice, #priceblock_dealprice").inner_text(timeout=10000)
        return price
    except PlaywrightTimeoutError:
        return f"Error: Size {size} not found"

SCRAPERS = {
    "Flipkart": scrape_flipkart,
    "Myntra": scrape_myntra,
    "Ajio": scrape_ajio,
    "Amazon": scrape_amazon
}

# === MAIN ===
async def main():
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for shoe in SHOES:
            results[shoe] = {}
            for size in SIZES:
                results[shoe][size] = {}
                for site, scraper in SCRAPERS.items():
                    try:
                        price = await scraper(page, shoe, size)
                        results[shoe][size][site] = price
                    except Exception as e:
                        results[shoe][size][site] = f"Error: {e}"
        await browser.close()

    # Prepare email content
    content = ""
    for shoe, sizes in results.items():
        content += f"=== {shoe} ===\n"
        for size, sites in sizes.items():
            for site, price in sites.items():
                content += f"{site} ({size}): {price}\n"
        content += "\n"

    # Send email
    message = Mail(
        from_email=EMAIL_FROM,
        to_emails=EMAIL_TO,
        subject="Daily Shoe Price Report",
        plain_text_content=content
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    asyncio.run(main())
