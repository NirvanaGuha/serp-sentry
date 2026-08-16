# serp-sentry

**Rank tracking that only speaks when something moved.**

`serp-sentry` checks Google's top 10 for your keywords weekly and pings you only on meaningful changes: **your** site gained or lost ground, a **new domain** cracked the top 10, or someone dropped out — with an optional AI gap-analysis of what the new entrant is doing that you aren't.

```
📊 SERP Sentry — example.com — 1 keyword(s) changed:

You slipped 4→7 on your money keyword while upstart.io entered at #4
with a listicle-style title — likely a fresher, more specific page.
Highest-leverage move: refresh your guide with 2026 examples.

❗ “cart abandonment emails”
   ▼ example.com: #4 → #7
   👀 new in top 10: upstart.io at #4 (17 Cart Abandonment Emails That Convert)
   · left top 10: rival.com (was #7)
```

**Quiet by design:** identical rankings say nothing; your own moves below a noise floor (default: 3 positions) are ignored; subdomains count as your site. Your own movements are marked ❗; other-domain churn is informational.

## Setup (≈3 minutes)

```bash
git clone https://github.com/NirvanaGuha/serp-sentry && cd serp-sentry
./install.sh
```

The wizard asks for your domain, your keywords (one per line), and a SERP data provider:

| Provider | Free tier | Get a key |
|---|---|---|
| **Serper.dev** (default) | 2,500 searches — years of weekly tracking | [serper.dev](https://serper.dev) → sign up → dashboard shows your key |
| SerpAPI | 100/month | [serpapi.com](https://serpapi.com) → sign up → "Api Key" |

Put the key in the `SERP_API_KEY` env var (the wizard walks you through it). Optionally add an AI for the gap-analysis — any OpenAI-compatible provider, table in [config.example.yaml](config.example.yaml); without it you get the raw ranking events.

First `serp-sentry run` baselines every keyword; then put the printed line on a weekly cron. Notifications via `SENTRY_SLACK_WEBHOOK` or `SENTRY_TELEGRAM_TOKEN` + `SENTRY_TELEGRAM_CHAT_ID` — click-path guides in the [repurposer README](https://github.com/NirvanaGuha/repurposer#notifications).

<details>
<summary><b>Run on GitHub Actions instead (no computer stays on)</b></summary>

1. **Fork** → edit `config.example.yaml` (domain, keywords, provider) → rename to `serp-sentry.yaml` → commit.
2. Settings → Secrets → Actions → add `SERP_API_KEY` (required), `LLM_API_KEY` and `SENTRY_*` webhooks (optional).
3. Actions tab → enable → "serp-sentry" → **Run workflow** (this takes the baseline). Runs Mondays after that.
</details>

## Budgeting searches

Each run costs one provider search per keyword. 20 keywords weekly ≈ 87 searches/month — 3.5% of Serper's free tier. Daily tracking of 20 keywords ≈ 600/month, still free.

## Tests

```bash
python tests/test_serp_sentry.py   # no network needed
```

Built on [growthkit](https://github.com/NirvanaGuha/growthkit). MIT license.
