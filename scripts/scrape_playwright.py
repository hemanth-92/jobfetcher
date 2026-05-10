import asyncio
import csv
import logging
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def scrape_linkedin_jobs(search_term, location, limit=5):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)

        # LinkedIn Guest Search URL
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={search_term.replace(' ', '%20')}&location={location.replace(' ', '%20')}"
        logger.info(f"Navigating to: {search_url}")
        
        try:
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # Wait for job cards to load
            await page.wait_for_selector(".base-card", timeout=10000)
            
            job_cards = await page.query_selector_all(".base-card")
            jobs = []
            
            for i, card in enumerate(job_cards[:limit]):
                title_el = await card.query_selector(".base-search-card__title")
                company_el = await card.query_selector(".base-search-card__subtitle")
                location_el = await card.query_selector(".job-search-card__location")
                link_el = await card.query_selector(".base-card__full-link")
                
                title = await title_el.inner_text() if title_el else "N/A"
                company = await company_el.inner_text() if company_el else "N/A"
                loc = await location_el.inner_text() if location_el else "N/A"
                link = await link_el.get_attribute("href") if link_el else "N/A"
                
                # Get Description (requires clicking)
                description = "N/A"
                if link_el:
                    try:
                        # Click to view description
                        await card.click()
                        await page.wait_for_selector(".show-more-less-html__markup", timeout=5000)
                        desc_el = await page.query_selector(".show-more-less-html__markup")
                        description = await desc_el.inner_text() if desc_el else "N/A"
                    except Exception as e:
                        logger.warning(f"Could not fetch description for job {i+1}: {e}")

                jobs.append({
                    "title": title.strip(),
                    "company": company.strip(),
                    "location": loc.strip(),
                    "url": link,
                    "description": description.strip(),
                    "site": "linkedin"
                })
                logger.info(f"Fetched: {title.strip()} at {company.strip()}")
            
            return jobs

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return []
        finally:
            await browser.close()

async def main():
    search_term = "Data Engineer"
    location = "United States"
    limit = 5
    
    jobs = await scrape_linkedin_jobs(search_term, location, limit)
    
    if jobs:
        # Save to CSV
        keys = jobs[0].keys()
        with open('jobs_playwright.csv', 'w', newline='', encoding='utf-8') as f:
            dict_writer = csv.DictWriter(f, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(jobs)
        
        # Save descriptions to TXT
        with open('job_descriptions_playwright.txt', 'w', encoding='utf-8') as f:
            for i, job in enumerate(jobs):
                f.write(f"JOB #{i+1}\n")
                f.write(f"TITLE: {job['title']}\n")
                f.write(f"COMPANY: {job['company']}\n")
                f.write(f"SITE: {job['site']}\n")
                f.write(f"URL: {job['url']}\n")
                f.write("-" * 40 + "\n")
                f.write(f"DESCRIPTION:\n{job['description']}\n")
                f.write("=" * 80 + "\n\n")
        
        logger.info(f"Successfully saved {len(jobs)} jobs.")
    else:
        logger.info("No jobs found.")

if __name__ == "__main__":
    asyncio.run(main())
