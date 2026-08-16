"""serp-sentry config: growthkit loader + this app's defaults."""
from pathlib import Path

from growthkit import config as kit_config

APP = "serp-sentry"

DEFAULTS = {
    "site_domain": None,             # required — e.g. example.com
    "keywords": [],                  # required — the queries to watch
    "top_n": 10,
    "min_position_change": 3,        # own-site moves smaller than this are noise
    "location": {"gl": "us", "hl": "en"},
    "serp": {
        "provider": "serper",        # serper | serpapi
        "api_key_env": "SERP_API_KEY",
    },
    "state_path": "~/.serp-sentry/state.json",
    "channels": {
        "stdout": True,
        "slack_webhook_env": "SENTRY_SLACK_WEBHOOK",
        "telegram_bot_token_env": "SENTRY_TELEGRAM_TOKEN",
        "telegram_chat_id_env": "SENTRY_TELEGRAM_CHAT_ID",
        "generic_webhook_env": "SENTRY_WEBHOOK_URL",
    },
    "narration": {                   # optional LLM gap-analysis; raw events without it
        "enabled": True,
        "base_url": "",
        "model": "",
        "api_key_env": "LLM_API_KEY",
        "extra_context": "",         # e.g. "We sell X; keywords 1-4 are money terms"
    },
}

_LEGACY = Path("serp-sentry.yaml")


def load_config(explicit: str | None = None) -> dict:
    if explicit is None and _LEGACY.exists():
        explicit = str(_LEGACY)
    cfg = kit_config.load(APP, DEFAULTS, required=("site_domain", "keywords"),
                          explicit=explicit)
    cfg["state_path"] = str(Path(str(cfg["state_path"])).expanduser())
    cfg["keywords"] = [k.strip() for k in cfg["keywords"] if str(k).strip()]
    if not cfg["keywords"]:
        raise ValueError("`keywords` is empty")
    return cfg
