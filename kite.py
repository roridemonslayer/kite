"""kite: posts new internship listings to one Slack channel.

Pulls the Simplify and vanshb03 Summer 2027 listing feeds, keeps the roles it
hasn't seen before, and posts them as a single message through a Slack
incoming webhook. A webhook is bound to exactly one channel, so the bot can
never post anywhere else.

    python kite.py --seed      # first run: remember everything, post nothing
    python kite.py --dry-run   # print what would be posted
    python kite.py             # post new roles (needs SLACK_WEBHOOK_URL)
"""
import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.request

try:  # macOS python.org builds ship without a CA bundle
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

FEEDS = {
    "Simplify": "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
    "vanshb03": "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json",
}
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
MAX_AGE = 3 * 86400       # ignore anything posted more than 3 days ago
MAX_PER_MESSAGE = 25      # Slack caps a message at 50 blocks
KEEP_SEEN = 30 * 86400    # forget keys after 30 days so seen.json stays small


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kite"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        return json.load(r)


def key(job):
    # the same role often shows up in both feeds, so dedupe on company + title
    norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    return norm(job["company_name"]) + "|" + norm(job["title"])


def load_jobs():
    jobs, now, ok = {}, time.time(), 0
    for name, url in FEEDS.items():
        try:
            feed = fetch(url)
            ok += 1
        except Exception as e:
            print(f"warning: {name} feed failed: {e}", file=sys.stderr)
            continue
        for j in feed:
            if not j.get("active", True) or not j.get("is_visible", True):
                continue
            if now - j.get("date_posted", 0) > MAX_AGE:
                continue
            jobs.setdefault(key(j), j)
    if not ok:
        # saving an empty seen.json here would make the next run repost everything
        sys.exit("every feed failed; leaving seen.json alone")
    return jobs


def load_seen():
    try:
        with open(STATE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_seen(seen):
    cutoff = time.time() - KEEP_SEEN
    seen = {k: t for k, t in seen.items() if t > cutoff}
    with open(STATE, "w") as f:
        json.dump(seen, f, indent=0, sort_keys=True)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def line(j):
    locs = j.get("locations") or []
    where = locs[0] + (f" +{len(locs) - 1}" if len(locs) > 1 else "") if locs else ""
    bits = [f"*{esc(j['company_name'])}*  <{j['url']}|{esc(j['title'])}>"]
    if where:
        bits.append(esc(where))
    if j.get("sponsorship") == "Does Not Offer Sponsorship":
        bits.append("no sponsorship")
    elif j.get("sponsorship") == "U.S. Citizenship is Required":
        bits.append("US citizens only")
    return "  ·  ".join(bits)


def message(jobs):
    n = len(jobs)
    blocks = [{"type": "header", "text": {"type": "plain_text",
               "text": f"🪁 {n} new internship{'s' if n != 1 else ''}"}}]
    for j in jobs:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": line(j)}})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
                   "text": "From the Simplify + vanshb03 Summer 2027 lists. Apply early 🫶"}]})
    return {"text": f"{n} new internships", "blocks": blocks, "unfurl_links": False}


def post(payload):
    req = urllib.request.Request(os.environ["SLACK_WEBHOOK_URL"],
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="mark current roles seen without posting")
    ap.add_argument("--dry-run", action="store_true", help="print instead of posting")
    args = ap.parse_args()

    jobs = load_jobs()
    seen = load_seen()
    now = time.time()
    if seen is None and not args.seed:
        sys.exit("no seen.json yet; run with --seed first so the channel isn't flooded")
    seen = seen or {}

    new = [j for k, j in jobs.items() if k not in seen]
    new.sort(key=lambda j: j.get("date_posted", 0))
    print(f"{len(jobs)} recent roles, {len(new)} new")

    if not args.seed and new:
        for i in range(0, len(new), MAX_PER_MESSAGE):
            payload = message(new[i:i + MAX_PER_MESSAGE])
            if args.dry_run:
                print("\n".join(line(j) for j in new[i:i + MAX_PER_MESSAGE]))
            else:
                post(payload)

    if not args.dry_run:
        for k in jobs:
            seen.setdefault(k, now)
        save_seen(seen)


if __name__ == "__main__":
    main()
