from html.parser import HTMLParser
from pathlib import Path
from PIL import Image
import re
import sys

ROOT = Path(__file__).resolve().parent
HTML_FILES = [ROOT / "index.html", ROOT / "privacy/index.html", ROOT / "terms/index.html"]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.h1 = 0
        self.titles = 0
        self.descriptions = 0
        self.links = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.h1 += 1
        elif tag == "title":
            self.titles += 1
        elif tag == "meta" and attrs.get("name") == "description" and attrs.get("content"):
            self.descriptions += 1
        elif tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        elif tag == "img":
            self.images.append(attrs)


def local_target(url: str) -> Path | None:
    prefix = "/kartiks-hermes/"
    if not url.startswith(prefix):
        return None
    relative = url[len(prefix):]
    target = ROOT / relative
    if url.endswith("/"):
        target /= "index.html"
    return target


errors = []
for page in HTML_FILES:
    text = page.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(text)
    if parser.h1 != 1:
        errors.append(f"{page}: expected one h1, found {parser.h1}")
    if parser.titles != 1:
        errors.append(f"{page}: expected one title, found {parser.titles}")
    if parser.descriptions != 1:
        errors.append(f"{page}: expected one meta description, found {parser.descriptions}")
    for link in parser.links:
        target = local_target(link)
        if target and not target.exists():
            errors.append(f"{page}: broken local link {link} -> {target}")
    for attrs in parser.images:
        if "alt" not in attrs:
            errors.append(f"{page}: image missing alt attribute: {attrs.get('src')}")
        target = local_target(attrs.get("src", ""))
        if target and not target.exists():
            errors.append(f"{page}: missing image {attrs.get('src')}")

all_text = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.rglob("*") if p.is_file() and p.suffix in {".html", ".css", ".md"})
secret_patterns = {
    "Google OAuth client ID": r"\d{10,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com",
    "Google authorization code": r"4/0A[A-Za-z0-9_-]+",
    "GitHub token": r"gh[opsu]_[A-Za-z0-9]{20,}",
}
for label, pattern in secret_patterns.items():
    if re.search(pattern, all_text):
        errors.append(f"possible secret found: {label}")

logo = ROOT / "assets/logo.png"
with Image.open(logo) as image:
    if image.size != (120, 120):
        errors.append(f"logo dimensions are {image.size}, expected 120x120")
    if image.format != "PNG":
        errors.append(f"logo format is {image.format}, expected PNG")
if logo.stat().st_size > 1_000_000:
    errors.append("logo exceeds Google's 1 MB limit")

required_privacy_phrases = [
    "accesses, uses, stores, and shares Google user data",
    "Google API Services User Data Policy",
    "Limited Use requirements",
    "does not sell Google user data",
    "Retention and deletion",
]
privacy = (ROOT / "privacy/index.html").read_text(encoding="utf-8")
for phrase in required_privacy_phrases:
    if phrase not in privacy:
        errors.append(f"privacy policy missing phrase: {phrase}")

if errors:
    print("VALIDATION_FAILED")
    print("\n".join(f"- {error}" for error in errors))
    sys.exit(1)

print("VALIDATION_OK")
print(f"pages={len(HTML_FILES)} logo_bytes={logo.stat().st_size}")
