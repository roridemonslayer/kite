# kite

A Slack bot that posts new internship and new grad roles to a single channel (built for ColorStack's `#opportunities`).

Every 30 minutes it checks about 3,000 company job boards directly (Workday, Greenhouse, Lever and Ashby): every company whose roles show up in the lists, plus a hand-picked set in `BOARDS`, so new roles show up before the lists add them. It also pulls the Summer 2027 internship and new grad lists from [Simplify](https://github.com/SimplifyJobs/Summer2027-Internships), [vanshb03](https://github.com/vanshb03/Summer2027-Internships) and [speedyapply](https://github.com/speedyapply/2027-SWE-College-Jobs). It skips anything posted more than 3 days ago or already sent (the same role on two lists only goes out once), and posts what is left: one message for internships and one for new grad roles.

It posts through a Slack **incoming webhook**, and a webhook is tied to one channel when it's created. That means the bot can't read messages, DM anyone or post in other channels.

## Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps), click **Create New App**, then **From a manifest**. Pick the workspace and paste in [`slack-manifest.json`](slack-manifest.json). That sets up the name, description and the single permission kite needs.
2. Click **Install to Workspace** and choose the channel to post in. In a workspace you don't admin, this sends an approval request to the admins.
3. Under **Incoming Webhooks**, copy the webhook URL. In this repo, go to **Settings → Secrets and variables → Actions** and add it as `SLACK_WEBHOOK_URL`.
4. The workflow in `.github/workflows/post.yml` runs every 30 minutes. To trigger a run by hand, use **Actions → post new internships → Run workflow**.

## Running locally

```sh
python3 kite.py --seed      # first run: mark current roles as seen, post nothing
python3 kite.py --dry-run   # print what would be posted
SLACK_WEBHOOK_URL=... python3 kite.py
```

`seen.json` tracks what has already been posted. The workflow commits it back after each run.

To add a company, put its board in `BOARDS` in `sources.py`. The slug is the part of its job board URL after `greenhouse.io/`, `jobs.lever.co/` or `jobs.ashbyhq.com/`.
