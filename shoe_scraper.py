import asyncio
import json
from playwright.async_api import async_playwright
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# Config
SHOES = [
    "Asics Novablast", "Asics Gel-Nimbus", "Saucony Kinvara", "Saucony Tempus",
    "Saucony Endorphin", "Brooks Ghost", "Brooks Adrenaline", "Brooks Glycerin",
    "Hoka Arahi", "Hoka Skyflow"
]
SIZES = ["UK 8", "UK 8.5", "UK 9"]

EMAIL_FROM = "your_verified_sendgrid_email@example.com"
EMAIL_TO = "your_gmail_here@gmail.com"
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")  # Set as secret in GitHub

# ---------------------- Flipkart Scraper ----------------------
async def scrape_flipkart(query):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"https://www.flipkart.com/search?q={query}", timeout=10000)

        # Extract JSON
        content = await page.content()
        start = content.find("window.__PRELOADED_STATE__ = ")
        if start != -1:
            start += len("window.__PRELOADED_STATE__ = ")
            end = content.find("};", start) + 1
            json_text = content[start:end]
            data = json.loads(json_text)
            try:
                products = data['product']['products']  # Stable path
                for p in products[:10]:
                    title = p.get('title', 'No title')
                    price = p.get('price', {}).get('value', 'Price not found')
                    url = "https://www.flipkart.com" + p.get('url', '')
                    results.append(f"{title} - ₹{price} - {url}")
            except KeyError:
                results.append("Could not extract products from JSON")
        await browser.close()
    return results

# ---------------------- Myntra Scraper (Stable) ----------------------
async def scrape_myntra(query):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = f"https://www.myntra.com/{query.replace(' ', '-')}"
        await page.goto(url, timeout=15000)

        try:
            # Try structured JSON first
            script = await page.locator('script[id="__NEXT_DATA__"]').inner_text(timeout=7000)
            data = json.loads(script)
            products = data["props"]["pageProps"]["searchResults"]["products"]
            for p in products[:10]:
                title = p.get("productName", "No title")
                price = p.get("price", {}).get("discounted", p.get("price", {}).get("mrp", "Price not found"))
                link = "https://www.myntra.com" + p.get("landingPageUrl", "")
                results.append(f"{title} - ₹{price} - {link}")

        except Exception as e_json:
            # Fallback: use visible HTML
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

        if not results:
            results.append("No Myntra results found (blocked or no data).")

        await browser.close()
    return results


# ---------------------- Ajio Scraper ----------------------
async def scrape_ajio(query):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"https://www.ajio.com/search/?text={query}", timeout=10000)

        # Extract products from JSON embedded in page
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
    return results

# ---------------------- Amazon Scraper (Stable) ----------------------
async def scrape_amazon(query):
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        search_url = f"https://www.amazon.in/s?k={query.replace(' ', '+')}"
        await page.goto(search_url, timeout=15000)

        try:
            # Wait for products to appear
            await page.wait_for_selector("div.s-main-slot div[data-component-type='s-search-result']", timeout=10000)
            products = page.locator("div.s-main-slot div[data-component-type='s-search-result']")
            count = min(10, await products.count())

            for i in range(count):
                try:
                    title = await products.nth(i).locator("h2 a span").inner_text(timeout=1000)
                    price_el = products.nth(i).locator("span.a-price span.a-offscreen")
                    price = await price_el.inner_text(timeout=1000) if await price_el.count() else "Price not found"
                    link_el = products.nth(i).locator("h2 a")
                    link = "https://www.amazon.in" + await link_el.get_attribute("href", timeout=1000)
                    results.append(f"{title} - {price} - {link}")
                except Exception:
                    continue

        except Exception as e_html:
            # Fallback: no products found
            content = await page.content()
            if "captcha" in content.lower():
                results.append("Amazon blocked this request (CAPTCHA shown).")
            else:
                results.append(f"Amazon failed: {type(e_html).__name__}")

        if not results:
            results.append("No Amazon results found (blocked or no data).")

        await browser.close()
    return results


# ---------------------- Send Email ----------------------
def send_email(subject, content):
    message = Mail(
        from_email=EMAIL_FROM,
        to_emails=EMAIL_TO,
        subject=subject,
        plain_text_content=content
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        print("Email sent successfully!")
    except Exception as e:
        print("Error sending email:", e)

# ---------------------- Main ----------------------
async def main():
    all_results = ""
    for shoe in SHOES:
        for size in SIZES:
            query = f"{shoe} {size}"
            all_results += f"\n=== {query} ===\n"

            flipkart = await scrape_flipkart(query)
            myntra = await scrape_myntra(query)
            ajio = await scrape_ajio(query)
            amazon = await scrape_amazon(query)

            all_results += "Flipkart:\n" + "\n".join(flipkart) + "\n"
            all_results += "Myntra:\n" + "\n".join(myntra) + "\n"
            all_results += "Ajio:\n" + "\n".join(ajio) + "\n"
            all_results += "Amazon:\n" + "\n".join(amazon) + "\n"

    send_email("Daily Shoe Prices", all_results)

# ---------------------- Run ----------------------
if __name__ == "__main__":
    asyncio.run(main())
