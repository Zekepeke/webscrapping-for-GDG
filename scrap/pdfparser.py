import fitz
import json
import ssl
import os
import urllib.request

# change this URL to point at any PDF you want to parse 
PDF_URL = (
    "https://catalog.purdue.edu/mime/media/7/2738/"
    "7+University+Regulations+and+Student+Conduct.pdf"
)

# output file - walks up from scrap/ to project root, then into data/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "purdue_regulations.json")

'''
Downloads a PDF from the given URL and returns its raw bytes.
SSL verification is disabled to handle self-signed or misconfigured certificates.
'''

def fetch_pdf_bytes(url: str) -> bytes:
    print(f"Fetching PDF from {url} ...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, context=ctx) as r:
        data = r.read()
    print(f"Fetched {len(data):,} bytes")
    return data

"""
Looks at a block's font size and boldness to classify it as:
- 'image'      if the block is an image
- 'heading'    if the text is large (>=16pt) or medium-large and bold (>=13pt)
- 'subheading' if the text is moderately sized and bold (>=11pt)
- 'body'       for everything else
"""
def classify_block(block: dict) -> str:
    if block["type"] != 0:
        return "image"

    lines = block.get("lines", [])
    if not lines:
        return "body"

    sizes, flags = [], []
    for line in lines:
        for span in line.get("spans", []):
            sizes.append(span.get("size", 0))
            flags.append(span.get("flags", 0))

    if not sizes:
        return "body"

    avg_size = sum(sizes) / len(sizes)
    is_bold = any(f & 2**4 for f in flags)

    if avg_size >= 16 or (avg_size >= 13 and is_bold):
        return "heading"
    if avg_size >= 11 and is_bold:
        return "subheading"
    return "body"


"""
Flattens a list of lines (each containing spans) into a single string.
Spans are the individual styled text chunks within a line — this joins
them together and separates lines with newlines.
"""
def spans_to_text(lines: list) -> str:
    parts = []
    for line in lines:
        line_text = "".join(span["text"] for span in line.get("spans", []))
        parts.append(line_text)
    return "\n".join(parts).strip()


"""
Core parser. Opens the PDF from raw bytes and iterates over every block
on every page. Uses classify_block() to determine if each block is a
heading, subheading, or body, then builds a nested JSON structure:
    - headings become top-level sections
    - subheadings become subsections under the current section
    - body text and images are attached to the nearest heading or subheading
Returns a dict with source URL, page count, and the parsed sections.
"""
def parse_pdf(pdf_bytes: bytes, source_url: str) -> dict:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    output = {
        "source": source_url,
        "total_pages": doc.page_count,
        "sections": [],
    }

    current_section = None
    current_subsection = None

    for page_num, page in enumerate(doc, start=1):
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in page_dict["blocks"]:
            if block["type"] == 1:  # image
                target = current_subsection or current_section
                if target:
                    target["content"].append({"type": "image", "page": page_num})
                continue

            text = spans_to_text(block.get("lines", []))
            if not text:
                continue

            kind = classify_block(block)

            if kind == "heading":
                current_section = {
                    "heading": text,
                    "page": page_num,
                    "content": [],
                    "subsections": [],
                }
                output["sections"].append(current_section)
                current_subsection = None

            elif kind == "subheading":
                current_subsection = {
                    "subheading": text,
                    "page": page_num,
                    "content": [],
                }
                if current_section is None:
                    current_section = {
                        "heading": "",
                        "page": page_num,
                        "content": [],
                        "subsections": [],
                    }
                    output["sections"].append(current_section)
                current_section["subsections"].append(current_subsection)

            else:
                entry = {"type": "text", "page": page_num, "text": text}
                if current_subsection is not None:
                    current_subsection["content"].append(entry)
                elif current_section is not None:
                    current_section["content"].append(entry)
                else:
                    output.setdefault("preamble", []).append(entry)

    doc.close()
    return output


"""
Entry point. Creates the output directory if it doesn't exist, fetches
the PDF, parses it, and writes the resulting JSON to OUTPUT_PATH.
"""

def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf_bytes = fetch_pdf_bytes(PDF_URL)

    print("Parsing PDF ...")
    data = parse_pdf(pdf_bytes, PDF_URL)

    print(f"Writing JSON to {OUTPUT_PATH} ...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done. {data['total_pages']} pages -> {len(data['sections'])} top-level sections.")


if __name__ == "__main__":
    main()