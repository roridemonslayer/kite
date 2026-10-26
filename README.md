# kite

A Slack bot that posts new internship listings to a single channel (built for ColorStack's `#opportunities`).

Every 20 minutes it pulls the [Simplify](https://github.com/SimplifyJobs/Summer2027-Internships) and [vanshb03](https://github.com/vanshb03/Summer2027-Internships) Summer 2027 lists, drops anything it has already posted, and sends the new roles as one message.

It posts through a Slack **incoming webhook**, and a webhook is tied to one channel when it's created. That means the bot can't read messages, DM anyone or post in other channels.

## Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**, then **From scratch**. Pick the workspace.
2. Under **Incoming Webhooks**, turn the feature on and click **Add New Webhook to Workspace**. Choose the channel. In a workspace you don't admin, this sends an approval request to the admins.
3. Copy the webhook URL. In this repo, go to **Settings → Secrets and variables → Actions** and add it as `SLACK_WEBHOOK_URL`.
4. The workflow in `.github/workflows/post.yml` runs every 20 minutes. To trigger a run by hand, use **Actions → post new internships → Run workflow**.

## Running locally

```sh
python3 kite.py --seed      # first run: mark current roles as seen, post nothing
python3 kite.py --dry-run   # print what would be posted
SLACK_WEBHOOK_URL=... python3 kite.py
```

`seen.json` tracks what has already been posted. The workflow commits it back after each run.
