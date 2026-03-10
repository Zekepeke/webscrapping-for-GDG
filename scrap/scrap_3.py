import requests
from bs4 import BeautifulSoup
import re


# ─────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────

POLICY_KEYWORDS = [
    "policy", "policies", "regulation", "procedure",
    "guidelines", "compliance", "code of conduct",
    "requirement", "university policy", "housing policy"
]

def score_page(url: str, title: str, text: str) -> int:
    """
    Score a page for Purdue Policy relevance.
      - Exact phrase 'purdue policy'  → +50 per hit  (very high)
      - Other policy keywords         → +10 per hit
      - Zero keyword hits             → -20 (not relevant)
    """
    score = 0
    combined = (url + " " + title + " " + text).lower()

    # Exact "purdue policy" — scored extremely high
    purdue_hits = len(re.findall(r"purdue\s+policy", combined))
    score += purdue_hits * 50

    for kw in POLICY_KEYWORDS:
        hits = combined.count(kw)
        score += hits * 10

    if score == 0:
        score = -20  # Nothing policy-related found

    return score


# ─────────────────────────────────────────────
# Your original scraper — extended with scoring
# ─────────────────────────────────────────────

def scrape_policy_page_final(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Unknown Title"

    policy_data = {
        "document_id": url.split('/')[-2],
        "title": title,
        "domain": "purdue.edu",
        "url": url,
        "effective_date": "",
        "last_revised": "",
        "sections": [],
        "score": 0  # filled after parsing
    }

    content_div = soup.find('div', class_='content')
    firstp = content_div.find('p') if content_div else None
    raw_text = firstp.get_text(separator='\n', strip=True) if firstp else ""

    for line in raw_text.split('\n'):
        if line.startswith("Date Issued"):
            policy_data["effective_date"] = line.replace("Date Issued:", "").strip()
        if line.startswith("Date Last Revised"):
            policy_data["last_revised"] = line.replace("Date Last Revised:", "").strip()

    all_section_text = []
    for header in soup.find_all('h2'):
        section_title = header.get_text(strip=True)
        section_text = []

        for sibling in header.find_next_siblings():
            if sibling.name == 'h2':
                break
            if sibling.name in ['p', 'ul', 'ol']:
                section_text.append(sibling.get_text(separator=' ', strip=True))

        if section_text:
            joined = "\n".join(section_text)
            policy_data["sections"].append({
                "section_title": section_title,
                "text": joined
            })
            all_section_text.append(joined)

    # Score using title + all section text combined
    full_text = " ".join(all_section_text)
    policy_data["score"] = score_page(url, title, full_text)

    return policy_data