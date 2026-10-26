"""Job sources for kite.

Each source returns a list of jobs in one shape:

    {"company", "title", "url", "locations": [...], "posted": unix time,
     "kind": "intern" | "newgrad", "sponsorship": str, "source": str}
"""
import html
import json
import re
import ssl
import time
import urllib.request

try:  # macOS python.org builds ship without a CA bundle
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

RAW = "https://raw.githubusercontent.com"


def fetch(url, as_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": "kite"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return json.load(r) if as_json else r.read().decode()


def listings_json(repo, kind):
    """The listings.json format used by the Simplify and vanshb03 repos."""
    def load():
        jobs = []
        for j in fetch(f"{RAW}/{repo}/dev/.github/scripts/listings.json"):
            if not j.get("active", True) or not j.get("is_visible", True):
                continue
            jobs.append({
                "company": j["company_name"], "title": j["title"], "url": j["url"],
                "locations": j.get("locations") or [], "posted": j.get("date_posted", 0),
                "kind": kind, "sponsorship": j.get("sponsorship", ""), "source": repo,
            })
        return jobs
    return load


def speedyapply(path, kind):
    """speedyapply keeps its lists as markdown tables with an Age column."""
    def cell(s):
        return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

    def load():
        jobs, now, cols = [], time.time(), None
        for row in fetch(f"{RAW}/speedyapply/2027-SWE-College-Jobs/main/{path}", False).splitlines():
            if not row.startswith("|"):
                cols = None
                continue
            parts = [p.strip() for p in row.strip().strip("|").split("|")]
            if parts[0] == "Company":
                cols = {name: i for i, name in enumerate(parts)}
                continue
            if not cols or set(parts[0]) <= set("-: "):
                continue
            link = re.search(r'href="([^"]+)"', parts[cols["Posting"]])
            age = re.match(r"(\d+)\s*([dhm])", cell(parts[cols["Age"]]))
            if not link or not age:
                continue
            n, unit = int(age.group(1)), age.group(2)
            ago = n * {"d": 86400, "h": 3600, "m": 60}[unit]
            jobs.append({
                "company": cell(parts[cols["Company"]]), "title": cell(parts[cols["Position"]]),
                "url": html.unescape(link.group(1)), "locations": [cell(parts[cols["Location"]])],
                "posted": now - ago, "kind": kind, "sponsorship": "", "source": "speedyapply",
            })
        return jobs
    return load


SOURCES = {
    "Simplify internships": listings_json("SimplifyJobs/Summer2027-Internships", "intern"),
    "vanshb03 internships": listings_json("vanshb03/Summer2027-Internships", "intern"),
    "Simplify new grad": listings_json("SimplifyJobs/New-Grad-Positions", "newgrad"),
    "vanshb03 new grad": listings_json("vanshb03/New-Grad-2027", "newgrad"),
    "speedyapply internships": speedyapply("README.md", "intern"),
    "speedyapply new grad": speedyapply("NEW_GRAD_USA.md", "newgrad"),
}
