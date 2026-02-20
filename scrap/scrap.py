import requests
from bs4 import BeautifulSoup
import json


def scrape_policy_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Structure to hold the scraped data
    policy_data = {
        "document_id": url.split('/')[-2], # Extracts 'ia4' from the URL
        "title": soup.find('h1').get_text(strip=True) if soup.find('h1') else "Unknown Title",
        "domain": "purdue.edu",
        "url": url,
        "effective_date": "", # TODO need to find specific HTML tag for this
        "sections": []
    }