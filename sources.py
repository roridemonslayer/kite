"""Job sources for kite.

Each source returns a list of jobs in one shape:

    {"company", "title", "url", "locations": [...], "posted": unix time,
     "kind": "intern" | "newgrad", "sponsorship": str, "source": str}
"""
import html
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

try:  # macOS python.org builds ship without a CA bundle
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

RAW = "https://raw.githubusercontent.com"


_cache = {}


def fetch(url, as_json=True, data=None):
    # the big listing feeds are read twice per run (jobs + board discovery)
    if data is None and (url, as_json) in _cache:
        return _cache[url, as_json]
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None, headers={
        "User-Agent": "kite", "Accept": "application/json", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        out = json.load(r) if as_json else r.read().decode()
    if data is None:
        _cache[url, as_json] = out
    return out


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


# Company job boards, read straight from the ATS so roles show up before the
# lists above pick them up. These are always checked; every other board that
# shows up in the lists gets found by discover_boards(). Name -> (ats, slug).
BOARDS = {
    "Stripe": ("greenhouse", "stripe"), "Airbnb": ("greenhouse", "airbnb"),
    "Figma": ("greenhouse", "figma"), "Databricks": ("greenhouse", "databricks"),
    "Robinhood": ("greenhouse", "robinhood"), "Coinbase": ("greenhouse", "coinbase"),
    "Discord": ("greenhouse", "discord"), "Reddit": ("greenhouse", "reddit"),
    "Pinterest": ("greenhouse", "pinterest"), "Dropbox": ("greenhouse", "dropbox"),
    "Lyft": ("greenhouse", "lyft"), "DoorDash": ("greenhouse", "doordashusa"),
    "Twitch": ("greenhouse", "twitch"), "Affirm": ("greenhouse", "affirm"),
    "Gusto": ("greenhouse", "gusto"), "Instacart": ("greenhouse", "instacart"),
    "Datadog": ("greenhouse", "datadog"), "Cloudflare": ("greenhouse", "cloudflare"),
    "MongoDB": ("greenhouse", "mongodb"), "Asana": ("greenhouse", "asana"),
    "Brex": ("greenhouse", "brex"), "Chime": ("greenhouse", "chime"),
    "Duolingo": ("greenhouse", "duolingo"), "Roblox": ("greenhouse", "roblox"),
    "Samsara": ("greenhouse", "samsara"), "Scale AI": ("greenhouse", "scaleai"),
    "Anthropic": ("greenhouse", "anthropic"), "Vercel": ("greenhouse", "vercel"),
    "Okta": ("greenhouse", "okta"), "Twilio": ("greenhouse", "twilio"),
    "Toast": ("greenhouse", "toast"), "Squarespace": ("greenhouse", "squarespace"),
    "Nuro": ("greenhouse", "nuro"), "Waymo": ("greenhouse", "waymo"),
    "SpaceX": ("greenhouse", "spacex"), "Verkada": ("greenhouse", "verkada"),
    "Flexport": ("greenhouse", "flexport"), "HubSpot": ("greenhouse", "hubspotjobs"),
    "Zscaler": ("greenhouse", "zscaler"), "SoFi": ("greenhouse", "sofi"),
    "Block": ("greenhouse", "block"), "Jump Trading": ("greenhouse", "jumptrading"),
    "Point72": ("greenhouse", "point72"), "IMC": ("greenhouse", "imc"),
    "Jane Street": ("greenhouse", "janestreet"), "Schonfeld": ("greenhouse", "schonfeld"),
    "Palantir": ("lever", "palantir"), "Spotify": ("lever", "spotify"),
    "Zoox": ("lever", "zoox"), "Shield AI": ("lever", "shieldai"),
    "Wealthfront": ("lever", "wealthfront"),
    "Ramp": ("ashby", "ramp"), "Notion": ("ashby", "notion"), "OpenAI": ("ashby", "openai"),
    "Linear": ("ashby", "linear"), "Cohere": ("ashby", "cohere"),
    "Perplexity": ("ashby", "perplexity"), "Replit": ("ashby", "replit"),
    "Supabase": ("ashby", "supabase"), "PostHog": ("ashby", "posthog"),
    "1Password": ("ashby", "1password"), "Skydio": ("ashby", "skydio"),
    "Rivian": ("ashby", "rivianvw.tech"), "Harvey": ("ashby", "harvey"),
    "Sierra": ("ashby", "sierra"), "Modal": ("ashby", "modal"),
    "ElevenLabs": ("ashby", "elevenlabs"), "Cursor": ("ashby", "cursor"),
    "Snowflake": ("ashby", "snowflake"),
    "Disney": ("workday", "disney/wd5/disneycareer"),
    "NVIDIA": ("workday", "nvidia/wd5/NVIDIAExternalCareerSite"),
    "Salesforce": ("workday", "salesforce/wd12/External_Career_Site"),
    "Netflix": ("workday", "netflix/wd108/netflix"),
    "Capital One": ("workday", "capitalone/wd12/Capital_One"),
}

# Where the lists' apply links point, so kite can read those boards directly.
DISCOVER_FROM = [
    f"{RAW}/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
    f"{RAW}/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
]
ATS_LINKS = [
    ("workday", re.compile(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[a-z]{2}/)?([a-z0-9_-]+)/", re.I)),
    ("greenhouse", re.compile(r"//(?:job-)?boards\.greenhouse\.io/([a-z0-9-]+)/jobs", re.I)),
    ("lever", re.compile(r"//jobs\.lever\.co/([a-z0-9.-]+)/", re.I)),
    ("ashby", re.compile(r"//jobs\.ashbyhq\.com/([a-z0-9.-]+)/", re.I)),
]
SKIP_SITES = re.compile(r"private|confidential|internal|staff|executive", re.I)
INTERN = re.compile(r"\bintern(ship)?\b|co-?op\b", re.I)
NEWGRAD = re.compile(r"new (college )?grad|university grad|recent grad|early career|entry[- ]level|\b202[67] grad", re.I)
# boards list every role at the company; keep the ones a CS student would want
TECH = re.compile(r"software|engineer|developer|\bswe\b|data|machine learning|\bml\b|\bai\b|research|"
                  r"quant|security|infrastructure|platform|product manag|technical|computer|robotics", re.I)


def discover_boards():
    found = {}
    for url in DISCOVER_FROM:
        for j in fetch(url):
            for ats, rx in ATS_LINKS:
                m = rx.search(j.get("url", ""))
                if m:
                    slug = "/".join(m.groups()) if ats == "workday" else m.group(1).lower()
                    found.setdefault((ats, slug), Counter())[j["company_name"]] += 1
    boards = {}
    for (ats, slug), names in found.items():
        # workday boards cost several requests each, so skip one-off and private sites
        if ats == "workday" and (sum(names.values()) < 2 or SKIP_SITES.search(slug)):
            continue
        boards[ats, slug] = names.most_common(1)[0][0]
    for name, key in BOARDS.items():
        boards[key] = name
    for name, root in CAREER_SITES.items():
        boards["careersite", root] = name
    return boards


def days_ago(posted_on):
    s = posted_on.lower()
    if "today" in s:
        return 0
    if "yesterday" in s:
        return 1
    m = re.search(r"(\d+)\+? days? ago", s)
    return int(m.group(1)) if m and "+" not in s else None


def workday(slug):
    tenant, wd, site = slug.split("/")
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    rows, now = [], time.time()
    for query, pages in (("intern", 3), ("new grad", 1)):
        for page in range(pages):
            posts = fetch(f"{base}/wday/cxs/{tenant}/{site}/jobs", data={
                "appliedFacets": {}, "limit": 20, "offset": page * 20, "searchText": query}).get("jobPostings", [])
            for j in posts:
                age = days_ago(j.get("postedOn", ""))
                if age is not None and "externalPath" in j:
                    rows.append((j["title"], f"{base}/en-US/{site}{j['externalPath']}",
                                 [j.get("locationsText", "")], now - age * 86400))
            if len(posts) < 20:
                break
    return rows


# Careers sites some big companies run themselves instead of a plain ATS page
# (Radancy "TalentBrew" sites). Name -> site root.
CAREER_SITES = {"Disney": "https://www.disneycareers.com"}
CAREER_SITE_QUERIES = ["software engineering intern", "technology intern", "data intern",
                       "engineering intern", "machine learning intern", "new grad software engineer"]


def career_site(company, root):
    rows, seen_urls = [], set()
    for q in CAREER_SITE_QUERIES:
        page = fetch(f"{root}/en/search-jobs/{urllib.parse.quote(q)}", as_json=False)
        for path, title, loc, date in re.findall(
                r'<a href="(/en/job/[^"]+)"[^>]*>\s*<h2>([^<]+)</h2>.*?job-location">([^<]*)<.*?job-date-posted">([^<]+)<',
                page, re.S):
            if path in seen_urls:
                continue
            seen_urls.add(path)
            posted = datetime.strptime(date.strip().replace(".", ""), "%b %d, %Y").timestamp()
            rows.append((html.unescape(title), root + path, [" ".join(html.unescape(loc).split())], posted))
    return rows


def iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def board(company, ats, slug):
    if ats == "greenhouse":
        rows = fetch(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")["jobs"]
        rows = [(j["title"], j["absolute_url"], [j["location"]["name"]],
                 iso(j.get("first_published") or j["updated_at"])) for j in rows]
    elif ats == "lever":
        rows = [(j["text"], j["hostedUrl"], j["categories"].get("allLocations") or [j["categories"].get("location", "")],
                 j["createdAt"] / 1000) for j in fetch(f"https://api.lever.co/v0/postings/{slug}?mode=json")]
    elif ats == "workday":
        rows = workday(slug)
    elif ats == "careersite":
        rows = career_site(company, slug)
    else:
        rows = [(j["title"], j["jobUrl"], [j["location"]] + [l["location"] for l in j.get("secondaryLocations", [])],
                 iso(j["publishedAt"])) for j in fetch(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")["jobs"]
                if j.get("isListed", True)]
    jobs = []
    for title, url, locs, posted in rows:
        title = title.strip()
        kind = "intern" if INTERN.search(title) else "newgrad" if NEWGRAD.search(title) else None
        if kind and TECH.search(title):
            jobs.append({"company": company, "title": title, "url": url, "locations": [l for l in locs if l],
                         "posted": posted, "kind": kind, "sponsorship": "", "source": f"{ats}:{slug}"})
    return jobs


def company_boards():
    boards = discover_boards()
    failed = []

    def one(item):
        (ats, slug), company = item
        try:
            return board(company, ats, slug)
        except Exception:  # one dead board shouldn't sink the rest
            failed.append(company)
            return []
    with ThreadPoolExecutor(32) as ex:
        jobs = [j for found in ex.map(one, boards.items()) for j in found]
    print(f"read {len(boards) - len(failed)} of {len(boards)} company job boards", file=sys.stderr)
    return jobs


SOURCES = {
    "Simplify internships": listings_json("SimplifyJobs/Summer2027-Internships", "intern"),
    "vanshb03 internships": listings_json("vanshb03/Summer2027-Internships", "intern"),
    "Simplify new grad": listings_json("SimplifyJobs/New-Grad-Positions", "newgrad"),
    "vanshb03 new grad": listings_json("vanshb03/New-Grad-2027", "newgrad"),
    "speedyapply internships": speedyapply("README.md", "intern"),
    "speedyapply new grad": speedyapply("NEW_GRAD_USA.md", "newgrad"),
    "company job boards": company_boards,
}
