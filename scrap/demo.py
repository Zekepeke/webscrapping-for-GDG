import requests
from bs4 import BeautifulSoup
import json


def scrape_policy_page():
    url = "https://purdue.edu/vpec/policies/academic-research-affairs/ia4/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Structure to hold the scraped data
    policy_data = {
        "document_id": "ia4_academic_freedom",
        "title": "Academic Freedom", 
        "domain": "purdue.edu",
        "url": url,
        "effective_date": "", 
        "sections": []
    }
    
    headings = soup.find_all('h2', class_='wp-block-heading')
    
    # Might need to change logic based on if the pages have different HTML structure
    for heading in headings:
        section_title = heading.get_text(strip=True)
        section_content = []
        
        # Iterate through siblings following this heading
        for sibling in heading.find_next_siblings():
            # Stop if hit next h2 section
            if sibling.name == 'h2':
                break
            
            # If paragraph or list, add its text to list
            if sibling.name in ['p', 'ul', 'ol']:
                section_content.append(sibling.get_text(separator=' ', strip=True))
        
        # Only add to dictionary if section has text
        if section_content:
            policy_data["sections"].append({
                "section_title": section_title,
                "text": "\n".join(section_content)
            })
            
    return policy_data

data = scrape_policy_page()
print(json.dumps(data, indent=4))