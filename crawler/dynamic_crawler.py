import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import time
import hashlib

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scrap import scrap_3
from firebase import firebase_write

MAX_LINKS = 30


def make_document_id(url: str) -> str:
    """Stable doc ID so repeated runs map the same URL to one Firestore doc."""
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
    return f"policy_{digest}"


def get_links(url: str, starter_url: str) -> list:
    """Fetch a page and return up to MAX_LINKS same-subdomain hrefs."""
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.content, 'html.parser')
        links = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(url, href).split('#')[0]
            parsed = urlparse(full_url)

            if parsed.netloc != urlparse(starter_url).netloc:
                continue
            if not parsed.path.startswith(urlparse(starter_url).path):
                continue
            if full_url not in links:
                links.append(full_url)
            if len(links) >= MAX_LINKS:
                break

        return links

    except Exception as e:
        print(f"[get_links] Error fetching {url}: {e}")
        return []


def crawler(starter_url: str, base_category: str, max_pages: int = 10):
    """
    DFS crawler:
      1. From each page, gather the first 30 hyperlinks
      2. Scrape each page
      3. Save all pages to Firebase, skipping duplicates
    """
    stack   = [starter_url]
    visited = set()
    all_data = []
    pages_crawled = 0
    uploaded_count = 0
    duplicate_count = 0

    existing_doc_ids, existing_urls = firebase_write.fetch_existing_policies()
    print(
        f"[Firebase] Found {len(existing_doc_ids)} existing policy docs; duplicates will be skipped."
    )

    while stack and pages_crawled < max_pages:
        url = stack.pop()

        if url in visited:
            continue

        print(f"[DFS] Crawling ({pages_crawled + 1}/{max_pages}): {url}")
        visited.add(url)
        pages_crawled += 1

        try:
            # ── Scrape ─────────────────────────────────────────
            page_data = scrap_3.scrape_policy_page_final(url)
            page_data["document_id"] = make_document_id(page_data["url"])
            page_data["category"] = base_category
            all_data.append(page_data)

            print(f"   Scraped — {page_data['title']}")

            # ── Save to Firebase, skipping duplicates ───────────
            doc_id   = page_data["document_id"]
            page_url = page_data["url"]

            if doc_id in existing_doc_ids or page_url in existing_urls:
                duplicate_count += 1
                print(f"   Skipping duplicate (already in Firebase): {page_data['title']}")
            else:
                wrote = firebase_write.upload_scraped_policy(page_data, skip_if_exists=True)
                if wrote:
                    uploaded_count += 1
                    existing_doc_ids.add(doc_id)
                    existing_urls.add(page_url)

            # ── Gather links → push unvisited onto stack ─────────
            links = get_links(url, starter_url)
            for link in reversed(links):
                if link not in visited:
                    stack.append(link)

            time.sleep(0.5)

        except Exception as e:
            print(f"[crawler] Error on {url}: {e}")
            continue

    # ── Output summary ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✅ Crawled {len(all_data)} page(s) total.\n")
    for d in all_data:
        print(f"   {d['title']}")
        print(f"   {d['url']}")

    # ── Save all data to local JSON ────────────────────────────
    output = {
        "summary": {
            "total_crawled":              len(all_data),
            "firebase_uploaded":          uploaded_count,
            "firebase_duplicates_skipped": duplicate_count,
        },
        "pages": all_data,
    }

    with open("policies.json", "w") as f:
        json.dump(output, f, indent=4)

    print(f"\n💾 Saved to policies.json  ({len(all_data)} total pages)")
    print(
        f"🔥 Firebase policies uploaded: {uploaded_count} | duplicates skipped: {duplicate_count}\n"
    )


# ── Entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    target_sites = [
        # Core Services
        {"url": "https://dining.purdue.edu", "category": "Dining"},
        {"url": "https://www.purdue.edu/treasurer/finance/bursar-office/", "category": "Financial/Bursar"},
        {"url": "https://housing.purdue.edu", "category": "Housing"},
        {"url": "https://www.purdue.edu/registrar/", "category": "Registrar"},
        {"url": "https://www.purdue.edu/dfa/", "category": "Financial Aid"},
        {"url": "https://admissions.purdue.edu", "category": "Admissions"},
        
        # Student Life & Health
        {"url": "https://www.purdue.edu/home/life-at-purdue/", "category": "Student Life"},
        {"url": "https://www.purdue.edu/push", "category": "Student Health (PUSH)"},
        {"url": "https://www.purdue.edu/odos/", "category": "Dean of Students"},
        {"url": "https://recwell.purdue.edu", "category": "Recreation (CoRec)"},
        
        # Academic & Research
        {"url": "https://catalog.purdue.edu", "category": "Purdue Catalog"},
        {"url": "https://gradschool.purdue.edu", "category": "Graduate School"},
        {"url": "https://lib.purdue.edu", "category": "Libraries"},
        {"url": "https://purdue.edu/research", "category": "Research"},
        {"url": "https://purdue.edu/academics", "category": "Colleges/Departments"},
        
        # Campus Services
        {"url": "https://it.purdue.edu", "category": "IT/ITaP"},
        {"url": "https://cco.purdue.edu", "category": "Career Center (CCO)"},
        {"url": "https://www.purdue.edu/parking/", "category": "Parking & Transit"},
        {"url": "https://purdue.edu/policies", "category": "Policies"},
        
        # Catalog - Colleges (add more as needed)
        {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24218", "category": "College of Engineering"},
        {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24224", "category": "College of Science"},
        {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24216", "category": "Daniels School of Business"},
        {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24220", "category": "College of Liberal Arts"},
        {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24203", "category": "Honors College"},
        
        # TODO: Add remaining college catalog URLs from your brainstorm list:
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24215", "category": "College of Agriculture"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24217", "category": "College of Education"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24219", "category": "College of Health and Human Sciences"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24222", "category": "Libraries and School of Information Studies"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24223", "category": "College of Pharmacy"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24221", "category": "Polytechnic Institute"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24225", "category": "College of Veterinary Medicine"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24231", "category": "Joint and Special Programs"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=24214", "category": "Purdue University in Indianapolis"},
        # {"url": "https://catalog.purdue.edu/content.php?catoid=18&navoid=2364", "category": "Exploratory Studies"},
    ]

    for site in target_sites:
        print(f"\n{'='*60}")
        print(f"Starting crawl for {site['category']}...")
        print(f"URL: {site['url']}")
        print('='*60)
        crawler(starter_url=site["url"], base_category=site["category"], max_pages=50)