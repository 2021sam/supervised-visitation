import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from bs4 import BeautifulSoup

POSITIVE = {"custody": 45, "parenting": 45, "parenting guide": 60, "custody and parenting": 80, "supervised visitation": 100, "visitation monitor": 100, "supervised exchange": 90, "professional monitor": 90, "referral list": 65, "family court services": 55, "family law": 40, "family and children": 35, "provider": 30}
NEGATIVE = {"jury": -60, "employment": -50, "traffic": -35, "criminal": -25}

def safe_public_url(url):
    """Basic URL validation; network-layer DNS/IP enforcement is required before public deployment."""
    p = urlparse(url)
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("Only ordinary http(s) URLs are supported")
    if p.hostname.lower() in ("localhost",) or p.hostname.lower().endswith((".local", ".internal")):
        raise ValueError("Local hostnames are not allowed")
    return url

def extract_links(html, base_url):
    safe_public_url(base_url)
    soup = BeautifulSoup(html, "html.parser")
    links = {}
    for a in soup.select("a[href]"):
        url, _ = urldefrag(urljoin(base_url, a.get("href", "")))
        try:
            safe_public_url(url)
        except ValueError:
            continue
        text = " ".join(a.stripped_strings)
        if url not in links:
            links[url] = {"url": url, "text": text[:250]}
    return list(links.values())

def rank_links(links):
    output = []
    for link in links:
        haystack = (link.get("text", "") + " " + link["url"].replace("-", " ").replace("_", " ")).lower()
        reasons = []
        score = 0
        for keyword, points in (*POSITIVE.items(), *NEGATIVE.items()):
            if keyword in haystack:
                score += points
                reasons.append(keyword)
        if re.search(r"\.pdf(?:$|\?)", link["url"], re.I):
            score += 8
            reasons.append("pdf")
        output.append({**link, "score": score, "reasons": reasons})
    return sorted(output, key=lambda x: (-x["score"], x["url"]))

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

def fingerprint(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def detect_html_directory(html):
    """Detect an unverified supervised visitation provider directory.

    Returns evidence when a page appears to contain a provider listing,
    otherwise returns None.
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.select(
        "script, style, nav, footer, header, noscript"
    ):
        tag.decompose()

    text = " ".join(soup.stripped_strings)
    normalized = re.sub(r"\s+", " ", text).lower()

    target = re.search(
        r"supervised[\s-]*(?:visitation|exchange)"
        r"|visitation[\s-]*monitor"
        r"|professional[\s-]*monitor",
        normalized,
    )

    if not target:
        return None

    headings = [
        " ".join(tag.stripped_strings).lower()
        for tag in soup.select("h1, h2, h3, caption")
    ]

    relevant_heading = any(
        re.search(
            r"supervised[\s-]*(?:visitation|exchange)"
            r"|visitation[\s-]*monitor"
            r"|professional[\s-]*monitor",
            heading,
        )
        for heading in headings
    )

    if not relevant_heading:
        return None

    entries = []

    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) >= 2:
            entries.append(" ".join(row.stripped_strings))

    if len(entries) < 2:
        for item in soup.select("main li, article li"):
            value = " ".join(item.stripped_strings)
            if len(value) >= 20:
                entries.append(value)

    if len(entries) < 2:
        return None

    provider_signals = sum(
        bool(
            re.search(
                r"provider|visitation|monitor|"
                r"family|contact|phone|email|"
                r"\(\d{3}\)|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",
                entry,
                re.I,
            )
        )
        for entry in entries
    )

    if provider_signals < 2:
        return None

    return {
        "entry_count": len(entries),
        "provider_signals": provider_signals,
        "relevant_heading": True,
    }
