import argparse
import asyncio
import csv
import logging
from urllib.parse import quote_plus

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)


async def scrape_linkedin_jobs(search_term: str, location: str, limit: int = 5) -> list[dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)

        search_url = (
            "https://www.linkedin.com/jobs/search/"
            f"?keywords={quote_plus(search_term)}&location={quote_plus(location)}"
        )
        logger.info("Navigating to: %s", search_url)

        try:
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
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

                description = "N/A"
                if link_el:
                    try:
                        await card.click()
                        await page.wait_for_selector(".show-more-less-html__markup", timeout=5000)
                        desc_el = await page.query_selector(".show-more-less-html__markup")
                        description = await desc_el.inner_text() if desc_el else "N/A"
                    except Exception as exc:
                        logger.warning("Could not fetch description for job %d: %s", i + 1, exc)

                jobs.append(
                    {
                        "title": title.strip(),
                        "company": company.strip(),
                        "location": loc.strip(),
                        "job_url": link,
                        "description": description.strip(),
                        "site": "linkedin",
                    }
                )
                logger.info("Fetched: %s at %s", title.strip(), company.strip())

            return jobs

        except Exception as exc:
            logger.error("Scraping failed: %s", exc)
            return []
        finally:
            await browser.close()


def save_jobs(
    jobs: list[dict],
    output_csv: str,
    descriptions_output: str,
) -> None:
    keys = jobs[0].keys()
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(jobs)

    with open(descriptions_output, "w", encoding="utf-8") as f:
        for i, job in enumerate(jobs):
            f.write(f"JOB #{i + 1}\n")
            f.write(f"TITLE: {job['title']}\n")
            f.write(f"COMPANY: {job['company']}\n")
            f.write(f"LOCATION: {job['location']}\n")
            f.write(f"SITE: {job['site']}\n")
            f.write(f"URL: {job['job_url']}\n")
            f.write("-" * 40 + "\n")
            f.write(f"DESCRIPTION:\n{job['description']}\n")
            f.write("=" * 80 + "\n\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Playwright-based LinkedIn job scraper")
    parser.add_argument("--search-term", default="Data Engineer", help="Job search keywords")
    parser.add_argument("--location", default="United States", help="Location to search")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of jobs to fetch")
    parser.add_argument("--output", default="jobs_playwright.csv", help="Output CSV path")
    parser.add_argument(
        "--descriptions-output",
        default="job_descriptions_playwright.txt",
        help="Output text file for job descriptions",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    jobs = await scrape_linkedin_jobs(args.search_term, args.location, args.limit)
    if not jobs:
        logger.info("No jobs found.")
        return

    save_jobs(jobs, args.output, args.descriptions_output)
    logger.info("Successfully saved %d jobs to %s", len(jobs), args.output)


if __name__ == "__main__":
    asyncio.run(main())