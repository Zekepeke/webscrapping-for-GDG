import fitz
import json
import ssl
import os
import urllib.request

PDF_URL = (
    "https://catalog.purdue.edu/mime/media/7/2738/"
    "7+University+Regulations+and+Student+Conduct.pdf"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "purdue_regulations.json")


def fetch_pdf_bytes(url: str) -> bytes:
    print(f"Fetching PDF from {url} ...")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, context=ctx) as r:
        data = r.read()
    print(f"Fetched {len(data):,} bytes")
    return data


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


def spans_to_text(lines: list) -> str:
    parts = []
    for line in lines:
        line_text = "".join(span["text"] for span in line.get("spans", []))
        parts.append(line_text)
    return "\n".join(parts).strip()


def parse_pdf(pdf_bytes: bytes, source_url: str) -> dict:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # ── Extract title from first heading found ──────────────────
    title = "Unknown Title"
    for page in doc:
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in page_dict["blocks"]:
            if classify_block(block) == "heading":
                title = spans_to_text(block.get("lines", []))
                break
        if title != "Unknown Title":
            break

    # ── Build document_id from URL (mirrors crawler logic) ──────
    parsed_path = source_url.rstrip('/').split('/')
    document_id = parsed_path[-1] if parsed_path else "unknown"

    # ── Extract domain ──────────────────────────────────────────
    from urllib.parse import urlparse
    domain = urlparse(source_url).netloc

    output = {
        "document_id":    document_id,
        "title":          title,
        "domain":         domain,
        "url":            source_url,
        "effective_date": "",
        "last_revised":   "",
        "sections":       [],
    }

    # ── Parse sections — flattened to match crawler format ──────
    current_section_title = None
    current_section_lines = []

    def flush_section():
        """Save the current section if it has content."""
        if current_section_title and current_section_lines:
            output["sections"].append({
                "section_title": current_section_title,
                "text": "\n".join(current_section_lines)
            })

    for page_num, page in enumerate(doc, start=1):
        page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        for block in page_dict["blocks"]:
            if block["type"] == 1:  # skip images
                continue

            text = spans_to_text(block.get("lines", []))
            if not text:
                continue

            kind = classify_block(block)

            if kind in ("heading", "subheading"):
                flush_section()                  # save previous section
                current_section_title = text
                current_section_lines = []

            else:  # body text
                # Check for date metadata before storing as section text
                for line in text.split('\n'):
                    if line.startswith("Date Issued"):
                        output["effective_date"] = line.replace("Date Issued:", "").strip()
                    elif line.startswith("Date Last Revised"):
                        output["last_revised"] = line.replace("Date Last Revised:", "").strip()
                    else:
                        current_section_lines.append(line)

    flush_section()  # don't forget the last section
    doc.close()
    return output


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    pdf_bytes = fetch_pdf_bytes(PDF_URL)

    print("Parsing PDF ...")
    data = parse_pdf(pdf_bytes, PDF_URL)

    print(f"Writing JSON to {OUTPUT_PATH} ...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Done. {len(data['sections'])} sections parsed.")


if __name__ == "__main__":
    main()