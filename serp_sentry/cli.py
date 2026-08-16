"""serp-sentry CLI: init | doctor | run | test-alert"""
import argparse
import json
import sys
from pathlib import Path

import yaml

from growthkit import channels as kit_channels
from growthkit import llm as kit_llm
from growthkit.state import State


def cmd_init(args):
    print("serp-sentry init — which rankings are we guarding?\n")
    site = input("Your domain (e.g. example.com): ").strip().removeprefix("https://") \
        .removeprefix("http://").strip("/")

    print("\nKeywords to watch, one per line (blank line to finish):")
    keywords = []
    while True:
        kw = input("  › ").strip()
        if not kw:
            break
        keywords.append(kw)
    if not keywords:
        print("No keywords — nothing to watch.")
        return 1

    print("\nSERP data provider (free tiers cover weekly tracking easily):")
    print("  1. Serper.dev  — 2,500 free searches, sign up at https://serper.dev")
    print("  2. SerpAPI     — 100 free/month, sign up at https://serpapi.com")
    p = input("Choice [1]: ").strip() or "1"
    provider = "serpapi" if p == "2" else "serper"
    import os
    if not os.environ.get("SERP_API_KEY"):
        key = input(f"Paste your {provider} API key: ").strip()
        if key:
            os.environ["SERP_API_KEY"] = key
            print("   (add `export SERP_API_KEY=...` to your ~/.zshrc to persist it)")

    from growthkit.llm import PROVIDER_TABLE
    print("\nAI gap-analysis when rankings change (optional). Any OpenAI-compatible API:")
    print(PROVIDER_TABLE)
    base_url = input("base_url (blank = raw ranking events only): ").strip()
    model = input("model name: ").strip() if base_url else ""

    cfg = {
        "site_domain": site,
        "keywords": keywords,
        "serp": {"provider": provider, "api_key_env": "SERP_API_KEY"},
        "narration": {"enabled": bool(base_url), "base_url": base_url,
                      "model": model, "api_key_env": "LLM_API_KEY"},
    }
    out = Path("serp-sentry.yaml")
    out.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    print(f"\n✓ Wrote {out.resolve()}")

    print("\nValidating with one live search...")
    from .providers import fetch_top, provider_ready
    ok, why = provider_ready(cfg["serp"])
    if not ok:
        print(f"  ✗ {why}")
    else:
        try:
            rows = fetch_top(cfg["serp"], keywords[0])
            print(f"  ✓ “{keywords[0]}” → #{rows[0]['position']} {rows[0]['domain']}"
                  if rows else "  ! search worked but returned no organic results")
        except Exception as e:
            print(f"  ✗ test search failed: {e}")

    print("\nOptional notifications: SENTRY_SLACK_WEBHOOK, SENTRY_TELEGRAM_TOKEN")
    print("+ SENTRY_TELEGRAM_CHAT_ID (see README).")
    print("\nNext: `serp-sentry run` — the first run baselines every keyword;")
    print("put it on a weekly cron after that.")


def cmd_doctor(args):
    ok = True
    try:
        from .config import load_config
        cfg = load_config(args.config)
        print(f"✓ config: {cfg['_config_path']} ({len(cfg['keywords'])} keywords, "
              f"site {cfg['site_domain']})")
    except Exception as e:
        print(f"✗ config: {e}")
        return 1

    from .providers import fetch_top, provider_ready
    p_ok, p_why = provider_ready(cfg["serp"])
    print(("✓ serp: " + p_why) if p_ok else ("✗ serp: " + p_why))
    ok = ok and p_ok
    if p_ok:
        try:
            rows = fetch_top(cfg["serp"], cfg["keywords"][0],
                             cfg["location"]["gl"], cfg["location"]["hl"],
                             cfg["top_n"])
            print(f"✓ live search: “{cfg['keywords'][0]}” returned {len(rows)} results")
        except Exception as e:
            print(f"✗ live search: {e}")
            ok = False

    healthy, line = kit_llm.doctor_line(cfg["narration"], required=False)
    print(line)
    for line in kit_channels.doctor_lines(cfg["channels"]):
        print(line)
    print(f"· state: {cfg['state_path']}")
    return 0 if ok else 1


def _analyze(cfg: dict, findings: list[dict]) -> str | None:
    n = cfg["narration"]
    if not n.get("enabled"):
        return None
    digest = []
    for f in findings:
        digest.append({
            "keyword": f["keyword"],
            "events": f["events"],
            "current_top": [{"pos": r["position"], "domain": r["domain"],
                             "title": r["title"]} for r in f["new"][:10]],
        })
    extra = n.get("extra_context") or ""
    prompt = (
        f"You are an SEO strategist for {cfg['site_domain']}. Weekly rank tracking "
        "detected these changes (JSON):\n\n" + json.dumps(digest, indent=1)
        + (f"\n\nContext: {extra}" if extra else "")
        + "\n\nWrite a short analysis (plain prose, no headers): for each keyword "
        "that changed, what happened and why it matters; for new entrants, what "
        "their page likely does that ours doesn't (infer from titles only — say "
        "so); end with the single highest-leverage action this week. Do not "
        "invent data."
    )
    return kit_llm.try_chat(n, prompt, max_tokens=600)


def cmd_run(args):
    from .config import load_config
    from .detect import compare, format_event, severity
    from .providers import fetch_top, provider_ready

    cfg = load_config(args.config)
    p_ok, p_why = provider_ready(cfg["serp"])
    if not p_ok:
        print(f"✗ {p_why}", file=sys.stderr)
        return 1

    state = State(cfg["state_path"])
    gl, hl = cfg["location"]["gl"], cfg["location"]["hl"]

    findings, baselined, failed = [], 0, 0
    for kw in cfg["keywords"]:
        try:
            new = fetch_top(cfg["serp"], kw, gl, hl, cfg["top_n"])
        except Exception as e:
            print(f"  ! fetch failed for “{kw}”: {e}", file=sys.stderr)
            failed += 1
            continue
        if not new:
            failed += 1
            continue
        key = f"serp:{kw}"
        old = state.get(key)
        state.set(key, new)
        if old is None:
            baselined += 1
            continue
        events = compare(old, new, cfg["site_domain"], cfg["min_position_change"])
        if events:
            findings.append({"keyword": kw, "events": events, "new": new})

    if baselined:
        print(f"[serp-sentry] baselined {baselined} keyword(s).")

    if not findings:
        print(f"[serp-sentry] No ranking changes across "
              f"{len(cfg['keywords'])} keywords"
              + (f" ({failed} fetch failures)" if failed else "") + ".")
        state.record_run({"keywords": len(cfg["keywords"]), "changes": 0})
        state.save()
        return 0

    analysis = _analyze(cfg, findings)
    lines = [f"📊 SERP Sentry — {cfg['site_domain']} — "
             f"{len(findings)} keyword(s) changed:", ""]
    if analysis:
        lines += [analysis, ""]
    for f in sorted(findings, key=lambda x: severity(x["events"]) != "high"):
        marker = "❗" if severity(f["events"]) == "high" else "·"
        lines.append(f"{marker} “{f['keyword']}”")
        for e in f["events"]:
            lines.append(f"   {format_event(e, cfg['site_domain'])}")
    text = "\n".join(lines)
    sent = kit_channels.send(text, cfg["channels"],
                             payload={"findings": [
                                 {"keyword": f["keyword"], "events": f["events"]}
                                 for f in findings]})
    print(f"\n[serp-sentry] digest sent to: {', '.join(sent)}", file=sys.stderr)
    state.record_run({"keywords": len(cfg["keywords"]),
                      "changes": len(findings)})
    state.save()
    return 0


def cmd_test_alert(args):
    from .config import load_config
    cfg = load_config(args.config)
    sent = kit_channels.send("serp-sentry test message — delivery works.",
                             cfg["channels"])
    print(f"Sent test message to: {', '.join(sent) or 'nowhere (no channels configured)'}")
    return 0


def main():
    p = argparse.ArgumentParser(
        prog="serp-sentry",
        description="Weekly rank tracking that only speaks when something moved: "
                    "your positions, new top-10 entrants, dropouts — with an "
                    "AI gap-analysis.")
    p.add_argument("--config", "-c", help="path to config YAML", default=None)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="interactive setup wizard")
    sub.add_parser("doctor", help="diagnose config, SERP provider, LLM, channels")
    sub.add_parser("run", help="track once (first run baselines; then cron weekly)")
    sub.add_parser("test-alert", help="send a test notification")

    args = p.parse_args()
    cmd = {"init": cmd_init, "doctor": cmd_doctor,
           "run": cmd_run, "test-alert": cmd_test_alert}[args.command]
    sys.exit(cmd(args) or 0)


if __name__ == "__main__":
    main()
