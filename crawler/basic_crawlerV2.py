"""
This is an extentension off of basic_crawler.py. it adds some image parsing.
throws it as extra information on the JSON
"""

import requests
from collections import deque
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from scrap import scrap_2_my_attempt
import hashlib


BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = os.path.join(BASE_DIR, "data", "images")

MIN_IMAGE_WIDTH  = 50
MIN_IMAGE_HEIGHT = 50

IMAGE_ATTRS = [
    ("img",    "src"),
    ("img",    "data-src")
]


def resolve_url(src, page_url):
    if not src or src.startswith("data:"):
        return None
    return urljoin(page_url, src.strip())


def download_image(img_url):
    try:
        resp = requests.get(img_url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"  Warning: could not download {img_url}: {e}")
        return None


def get_image_dimensions(img_bytes):
    if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        w = int.from_bytes(img_bytes[16:20], "big")
        h = int.from_bytes(img_bytes[20:24], "big")
        return w, h
    if img_bytes[:2] == b'\xff\xd8':
        i = 2
        while i < len(img_bytes) - 8:
            if img_bytes[i] != 0xFF:
                break
            marker = img_bytes[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h = int.from_bytes(img_bytes[i + 5:i + 7], "big")
                w = int.from_bytes(img_bytes[i + 7:i + 9], "big")
                return w, h
            length = int.from_bytes(img_bytes[i + 2:i + 4], "big")
            i += 2 + length
    return 0, 0


def guess_extension(img_bytes, fallback_url):
    sigs = {b'\x89PNG': "png", b'\xff\xd8': "jpg",
            b'GIF8': "gif", b'RIFF': "webp"}
    for sig, ext in sigs.items():
        if img_bytes[:len(sig)] == sig:
            return ext
    path = urlparse(fallback_url).path
    if "." in path:
        return path.rsplit(".", 1)[-1].lower()[:5]
    return "bin"


def extract_images(soup, page_url, document_id, seen_hashes):
    os.makedirs(IMAGE_DIR, exist_ok=True)
    image_records = []

    candidate_urls = []
    for tag, attr in IMAGE_ATTRS:
        for el in soup.find_all(tag):
            raw = el.get(attr, "")
            if attr == "srcset":
                raw = raw.split(",")[0].split()[0]
            abs_url = resolve_url(raw, page_url)
            if abs_url:
                candidate_urls.append(abs_url)

    for img_url in candidate_urls:
        img_bytes = download_image(img_url)
        if not img_bytes:
            continue

        width, height = get_image_dimensions(img_bytes)
        if 0 < width < MIN_IMAGE_WIDTH or 0 < height < MIN_IMAGE_HEIGHT:
            continue

        img_hash = hashlib.md5(img_bytes).hexdigest()
        if img_hash in seen_hashes:
            continue
        seen_hashes.add(img_hash)

        ext      = guess_extension(img_bytes, img_url)
        filename = f"{document_id}_{img_hash[:8]}.{ext}"
        filepath = os.path.join(IMAGE_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(img_bytes)

        image_records.append({
            "filename":    filename,
            "source_url":  img_url,
            "width":       width,
            "height":      height,
            "format":      ext,
            "md5":         img_hash,
            "description": "", #LLM
            "image_type":  "", #Classifier
            "public_url":  "", #storage
        })

        print(f"  Saved image: {filename} ({width}x{height})")

    return image_records


def crawler(starter_url, max_depth=10):
    queue = deque([(starter_url)]) # start queue with the starter url
    visited = set() #creates hashtable
    pages_crawled = 0
    all_data = [] # List to hold data from all crawled pages
    seen_hashes = set()
    
    while queue and pages_crawled < max_depth:
        url = queue.popleft()
        if url in visited:
            continue

        print(f"Crawling: {url}")

        try:
            r = requests.get(url)
            if r.status_code != 200:
                print(f"Failed to retrieve {url} (status code: {r.status_code})")
                continue
            
            visited.add(url)
            pages_crawled += 1

            soup = BeautifulSoup(r.content, 'html.parser')
            page_data = scrap_2_my_attempt.scrape_policy_page_final(url)

            document_id = url.split('/')[-2]
            page_data["images"] = extract_images(soup, url, document_id, seen_hashes)

            for link in soup.find_all('a'):
                href = link.get('href')
                if not href:
                    continue
                
                full_url = urljoin(url, href)
                full_url = full_url.split('#')[0] #remove any fragment identifiers
                parsed_url = urlparse(full_url)

                if parsed_url.netloc != "www.housing.purdue.edu":
                    continue
                
                current_depth = urlparse(url).path.count('/')
                new_depth = parsed_url.path.count('/')

                if new_depth >= current_depth and full_url not in visited:
                    queue.append(full_url)


            all_data.append(page_data)
            time.sleep(0.5) #make it easier

        except Exception as e:
            print(f"Error crawling {url}: {e}")
            continue
            
    with open(os.path.join(BASE_DIR, "data", "housing.json"), "w") as f:
        json.dump(all_data, f, indent=4)
    print(f"Saved {len(all_data)} pages to housing.json")

starter_url = "https://www.housing.purdue.edu/my-housing/options/residence-halls/"
crawler(starter_url, max_depth=25)  # small max_depth for testing