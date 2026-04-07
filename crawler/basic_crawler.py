import requests
from collections import deque
from scrap import scrap_3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import time
import hashlib


def generate_document_id(url: str) -> str:
    """Generate a unique document ID from URL using hash prefix."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    path_segment = urlparse(url).path.strip('/').split('/')[-1] or "index"
    return f"policy_{path_segment}_{url_hash}"


def infer_category(url: str) -> tuple[str, str]:
    """
    Infer category and sub_category from URL path.
    TODO: Enhance this with more sophisticated extraction logic in scrap_3.py
    if needed, or use page content analysis.
    """
    path = urlparse(url).path.lower()
    
    # Category mappings based on URL patterns
    category_map = {
        "housing": ("Student Life", "Housing Policies"),
        "residential": ("Student Life", "Residential Life"),
        "financial-aid": ("Financial Services", "Financial Aid"),
        "financialaid": ("Financial Services", "Financial Aid"),
        "bursar": ("Financial Services", "Bursar"),
        "tuition": ("Financial Services", "Tuition & Fees"),
        "registrar": ("Academic Services", "Registrar"),
        "academic": ("Academic Services", "Academic Policies"),
        "conduct": ("Student Life", "Student Conduct"),
        "dean": ("Academic Services", "Dean of Students"),
        "admissions": ("Academic Services", "Admissions"),
        "scholarship": ("Financial Services", "Scholarships"),
    }
    
    for key, (cat, subcat) in category_map.items():
        if key in path:
            return cat, subcat
    
    return "General", "University Policies"


def crawler(starter_url, max_depth=10):
    # Store tuples of (current_url, parent_url) for parent tracking
    queue = deque([(starter_url, None)])
    visited = set()
    pages_crawled = 0
    all_data = []
    
    while queue and pages_crawled < max_depth:
        url, parent_url = queue.popleft()
        
        if url in visited:
            continue

        print(f"Crawling: {url}")
        if parent_url:
            print(f"  └─ Parent: {parent_url}")

        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                print(f"Failed to retrieve {url} (status code: {r.status_code})")
                continue
            
            visited.add(url)
            pages_crawled += 1

            soup = BeautifulSoup(r.content, 'html.parser')
            page_data = scrap_3.scrape_policy_page_final(url)

            # Inject parent_url into page_data
            page_data["parent_url"] = parent_url
            
            # Generate a proper document_id
            page_data["document_id"] = generate_document_id(url)
            
            # Infer category and sub_category from URL
            # TODO: If scrap_3.py extracts these from page content, use those instead
            category, sub_category = infer_category(url)
            page_data["category"] = category
            page_data["sub_category"] = sub_category

            for link in soup.find_all('a'):
                href = link.get('href')
                if not href:
                    continue
                
                full_url = urljoin(url, href)
                full_url = full_url.split('#')[0]
                parsed_url = urlparse(full_url)

                # Allow purdue.edu subdomains (housing.purdue.edu, www.purdue.edu, etc.)
                if not parsed_url.netloc.endswith("purdue.edu"):
                    continue
                
                current_depth = urlparse(url).path.count('/')
                new_depth = parsed_url.path.count('/')

                if new_depth >= current_depth and full_url not in visited:
                    # Pass current URL as parent_url for child links
                    queue.append((full_url, url))

            all_data.append(page_data)
            time.sleep(0.5)

        except Exception as e:
            print(f"Error crawling {url}: {e}")
            continue
    
    # Build flat output structure optimized for RAG
    output = {
        "metadata": {
            "starter_url": starter_url,
            "pages_crawled": len(all_data),
            "crawl_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "relevant_pages": [
            page for page in all_data if page.get("relevant", False)
        ],
        "all_pages": all_data
    }
            
    with open("policies.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\nCrawl complete:")
    print(f"  Total pages: {len(all_data)}")
    print(f"  Relevant pages: {len(output['relevant_pages'])}")
    print(f"  Saved to policies.json")


if __name__ == "__main__":
    starter_url = "https://www.housing.purdue.edu/"
    crawler(starter_url, max_depth=5)