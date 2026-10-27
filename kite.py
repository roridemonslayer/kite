"""kite: posts new internship and new grad roles to one Slack channel.

Pulls several job lists (see sources.py), keeps roles posted in the last 3
days that it hasn't seen before, and posts them through a Slack incoming
webhook. A webhook is bound to exactly one channel, so the bot can never post
anywhere else.

    python kite.py --seed      # first run: remember everything, post nothing
    python kite.py --dry-run   # print what would be posted
    python kite.py --browser   # show what would be posted as a page in the browser
    python kite.py             # post new roles (needs SLACK_WEBHOOK_URL)
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.request
import webbrowser

from sources import CTX, SOURCES

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
MAX_DAYS = 3              # post roles from today and the 3 days before, nothing older
MAX_PER_MESSAGE = 45      # Slack caps a message at 50 blocks
KEEP_SEEN = 30 * 86400    # forget keys after 30 days so seen.json stays small
BLOCKED = {"astrolab"}    # companies never to post, lowercase with no spaces
KINDS = {"intern": "new internship", "newgrad": "new grad role"}


def norm(s):
    s = (s or "").lower()
    # lists word the same role differently ("SWE Intern - Summer 2027 - USA")
    s = re.sub(r"\b((summer|fall|spring|winter)\s*)?20\d\d\b|\b(usa|us|united states)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def norm_company(s):
    # lists name the same employer differently ("General Dynamics Mission
    # Systems, Inc." vs "General Dynamics Mission Systems")
    s = re.sub(r"\s+-\s+.*$", "", s or "")
    s = re.sub(r"[,.]?\s+(inc|llc|l\.l\.c|ltd|corp|corporation|co|company|plc|lp)\.?$", "", s.strip(), flags=re.I)
    return norm(s)


def keys(job):
    # a role counts as seen if either its company + title or its link was seen
    url = job["url"].lower()
    gh = re.search(r"gh_jid=(\d+)|greenhouse\.io/[^/]+/jobs/(\d+)", url)
    if gh:  # one greenhouse job shows up under many different links
        url = "greenhouse:" + (gh.group(1) or gh.group(2))
    else:
        url = re.sub(r"[?&](utm_[a-z]+|source|ref|embed)=[^&]*", "", url)
        url = re.sub(r"^https?://(www\.)?", "", url).rstrip("/?")
    return [norm_company(job["company"]) + "|" + norm(job["title"]), url]


def load_jobs():
    jobs, ok = [], 0
    # count by calendar day: many sites only give a date, so "posted Oct 23"
    # should still count on Oct 26
    today = datetime.date.today()
    cutoff = time.mktime((today - datetime.timedelta(days=MAX_DAYS)).timetuple())
    for name, load in SOURCES.items():
        try:
            found = load()
            ok += 1
        except Exception as e:
            print(f"warning: {name} failed: {e}", file=sys.stderr)
            continue
        jobs += [j for j in found if j["posted"] >= cutoff and norm(j["company"]) not in BLOCKED]
    if not ok:
        # saving an empty seen.json here would make the next run repost everything
        sys.exit("every source failed; leaving seen.json alone")
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
    bits = [f"*{esc(j['company'])}*  <{j['url']}|{esc(j['title'])}>"]
    if where:
        bits.append(esc(where))
    if j.get("sponsorship") == "Does Not Offer Sponsorship":
        bits.append("no sponsorship")
    elif j.get("sponsorship") == "U.S. Citizenship is Required":
        bits.append("US citizens only")
    return "  ·  ".join(bits)


def message(jobs, kind):
    n, label = len(jobs), KINDS[kind]
    title = f"🪁 {n} {label}{'s' if n != 1 else ''}"
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": title}}]
    for j in jobs:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": line(j)}})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
                   "text": "Posted in the last 3 days, from company job boards and the Simplify, vanshb03 and speedyapply lists. Apply early 🫶"}]})
    return {"text": title, "blocks": blocks, "unfurl_links": False}


def page(batches):
    # a local look at what the next run would post, laid out like the Slack messages
    def item(j):
        locs = j.get("locations") or []
        where = locs[0] + (f" +{len(locs) - 1}" if len(locs) > 1 else "") if locs else ""
        tags = "".join(f'<span class="tag">{t}</span>' for t, on in
                       [("no sponsorship", j.get("sponsorship") == "Does Not Offer Sponsorship"),
                        ("US citizens only", j.get("sponsorship") == "U.S. Citizenship is Required")] if on)
        return (f'<li><b>{esc(j["company"])}</b> <a href="{esc(j["url"])}" target="_blank">{esc(j["title"])}</a>'
                f'<span class="where">{esc(where)}</span>{tags}</li>')
    msgs = "".join(f'<section><h2>{esc(message(chunk, kind)["text"])}</h2><ul>{"".join(item(j) for j in chunk)}</ul></section>'
                   for kind, chunk in batches)
    return f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>kite preview</title>
<style>
body{{margin:0;background:#0d0d0d;color:#eee;font:15px/1.5 -apple-system,system-ui,sans-serif}}
main{{max-width:860px;margin:0 auto;padding:32px 16px}}
h1{{font-size:44px;margin:0;letter-spacing:-1px}} h1 span{{color:#c6f432}}
p.sub{{color:#888;margin:4px 0 28px}}
section{{background:#171717;border:1px solid #262626;border-radius:16px;padding:20px 22px;margin-bottom:20px}}
h2{{margin:0 0 12px;font-size:20px}}
ul{{list-style:none;margin:0;padding:0}} li{{padding:8px 0;border-top:1px solid #222}}
a{{color:#c6f432;text-decoration:none}} a:hover{{text-decoration:underline}}
.where{{color:#888;margin-left:8px}} .where:empty{{display:none}}
.tag{{font-size:12px;background:#2a2a2a;color:#ccc;border-radius:99px;padding:1px 8px;margin-left:8px}}
</style><main><h1>kite <span>preview</span></h1>
<p class="sub">What the next run would post · {datetime.datetime.now():%b %d, %I:%M %p} · nothing was posted or marked seen</p>
{msgs or "<p>No new roles right now.</p>"}</main>"""


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
    ap.add_argument("--browser", action="store_true", help="show what would be posted in the browser")
    args = ap.parse_args()
    if args.browser:
        args.dry_run = True

    jobs = load_jobs()
    seen = load_seen()
    now = time.time()
    if seen is None and not args.seed:
        sys.exit("no seen.json yet; run with --seed first so the channel isn't flooded")
    seen = seen or {}

    new, taken = [], set()
    for j in sorted(jobs, key=lambda j: j["posted"]):
        ks = keys(j)
        if not any(k in seen or k in taken for k in ks):
            new.append(j)
        taken.update(ks)
    print(f"{len(jobs)} recent listings, {len(new)} new")

    if not args.seed and not args.dry_run and not os.environ.get("SLACK_WEBHOOK_URL"):
        # no channel hooked up yet: keep seen.json current so the first real
        # post isn't a backlog of everything since the repo went up
        print("no SLACK_WEBHOOK_URL set; marking roles seen without posting")
        args.seed = True

    if not args.seed:
        batches = []
        for kind in KINDS:
            batch = [j for j in new if j["kind"] == kind]
            for i in range(0, len(batch), MAX_PER_MESSAGE):
                chunk = batch[i:i + MAX_PER_MESSAGE]
                if args.browser:
                    batches.append((kind, chunk))
                elif args.dry_run:
                    print(f"\n== {message(chunk, kind)['text']}")
                    print("\n".join(line(j) for j in chunk))
                else:
                    post(message(chunk, kind))
        if args.browser:
            out = os.path.join(os.path.dirname(STATE), "preview.html")
            with open(out, "w") as f:
                f.write(page(batches))
            webbrowser.open("file://" + out)
            print("opened", out)

    if not args.dry_run:
        for k in taken:
            seen.setdefault(k, now)
        save_seen(seen)

if __name__ == "__main__":
    main()
