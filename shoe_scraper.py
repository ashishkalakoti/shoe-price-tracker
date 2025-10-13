import os
import asyncio
from playwright.async_api import async_playwright
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# --------------------------
# CONFIGURATION
# --------------------------
shoes = [
    "Asics Novablast",
    "Asics Gel-Nimbus",
    "Saucony Kinvara",
    "Saucony Tempus",
    "Saucony Endorphin",
    "Brooks Ghost",
    "Brooks Adrenaline",
    "Brooks Glycerin",
    "Hoka Arahi",
    "Hoka Skyflow"
]

sizes = ["UK 8", "UK 8.5", "UK 9"]

# Emails from GitHub Secrets
EMAIL_FROM = os.environ.get("EMAIL_FROM")  # e.g. alerts@shoes.com
EMAIL_TO = os.environ.get("EMAIL_TO")      # your Gmail
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")

# --------------------------
# WEBSITE URL TEMPLATES
# --------------------------
websites = {
    "Flipkart": "https://www.flipkart.com/search?q={query}",
    "Myntra": "https://www.myntra.com/{query}",
    "Ajio": "https://www.ajio.com/search/?text={query}",
    "Amazon": "https://www.amazon.in/s?k={query.replace(' ', '+')}"
}

# --------------------------
# SCRAPER FUNCTION
# --------------------------
async def scrape_shoe(page, url, shoe, size):
    await page.goto(url)
    await page.wait_for_load_state("domcontentloaded")
    
    # Flipkart: Select size and extract price
    if "flipkart" in url:
        try:
            size_selector = f"button[title='{size}']"
            await page.click(size_selector)
            price = await page.inner_text("._30jeq3")
            return f"Flipkart: {shoe} {size} - ₹{price}"
        except Exception as e:
            return f"Flipkart: Error selecting size {size} for {shoe} - {str(e)}"
    
    # Amazon: Select size and extract price
    elif "amazon" in url:
        try:
            size_selector = f"span[data-asin='{size}']"
            await page.click(size_selector)
            price = await page.inner_text(".a-price .a-offscreen")
            return f"Amazon: {shoe} {size} - ₹{price}"
        except Exception as e:
            return f"Amazon: Error selecting size {size} for {shoe} - {str(e)}"
    
    # Myntra: Extract price
    elif "myntra" in url:
        try:
            price = await page.inner_text(".pdp-price")
            return f"Myntra: {shoe} {size} - ₹{price}"
        except Exception as e:
            return f"Myntra: Error extracting price for {shoe} {size} - {str(e)}"
    
    # Ajio: Extract price
    elif "ajio" in url:
        try:
            price = await page.inner_text(".prod-sp")
            return f"Ajio: {shoe} {size} - ₹{price}"
        except Exception as e:
            return f"Ajio: Error extracting price for {shoe} {size} - {str(e)}"
    
    return f"Unknown site: {shoe} {size}"

# --------------------------
# MAIN FUNCTION
# --------------------------
async def main():
    summary = ""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        for shoe in shoes:
            summary += f"\n=== {shoe} ===\n"
            for site, url_template in websites.items():
                url = url_template.format(query=shoe.replace(" ", "+"))
                for size in sizes:
                    result = await scrape_shoe(page, url, shoe, size)
                    summary += f"{result}\n"
        
        await browser.close()

    # --------------------------
    # SEND EMAIL VIA SENDGRID
    # --------------------------
    message = Mail(
        from_email=EMAIL_FROM,
        to_emails=EMAIL_TO,
        subject="Daily Shoe Price Report",
        plain_text_content=summary
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

# Run the async main
if __name__ == "__main__":
    asyncio.run(main())
