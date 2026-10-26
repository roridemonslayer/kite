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
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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


# Company job boards, read straight from the ATS so roles show up before the
# lists above pick them up. Name -> (ats, board slug).
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
}
INTERN = re.compile(r"\bintern(ship)?\b|co-?op\b", re.I)
NEWGRAD = re.compile(r"new (college )?grad|university grad|recent grad|early career|entry[- ]level|\b202[67] grad", re.I)
# boards list every role at the company; keep the ones a CS student would want
TECH = re.compile(r"software|engineer|developer|\bswe\b|data|machine learning|\bml\b|\bai\b|research|"
                  r"quant|security|infrastructure|platform|product manag|technical|computer|robotics", re.I)


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
    def one(item):
        try:
            return board(item[0], *item[1])
        except Exception as e:  # one dead board shouldn't sink the rest
            print(f"warning: {item[0]} board failed: {e}", file=sys.stderr)
            return []
    with ThreadPoolExecutor(16) as ex:
        return [j for jobs in ex.map(one, BOARDS.items()) for j in jobs]


SOURCES = {
    "Simplify internships": listings_json("SimplifyJobs/Summer2027-Internships", "intern"),
    "vanshb03 internships": listings_json("vanshb03/Summer2027-Internships", "intern"),
    "Simplify new grad": listings_json("SimplifyJobs/New-Grad-Positions", "newgrad"),
    "vanshb03 new grad": listings_json("vanshb03/New-Grad-2027", "newgrad"),
    "speedyapply internships": speedyapply("README.md", "intern"),
    "speedyapply new grad": speedyapply("NEW_GRAD_USA.md", "newgrad"),
    "company job boards": company_boards,
}
