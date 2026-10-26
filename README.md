# kite

A Slack bot that posts new internship and new grad roles to a single channel (built for ColorStack's `#opportunities`).

Every 20 minutes it pulls the Summer 2027 internship and new grad lists from [Simplify](https://github.com/SimplifyJobs/Summer2027-Internships), [vanshb03](https://github.com/vanshb03/Summer2027-Internships) and [speedyapply](https://github.com/speedyapply/2027-SWE-College-Jobs). It skips anything posted more than 3 days ago or already sent (the same role on two lists only goes out once), then posts what is left: one message for internships and one for new grad roles.

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
