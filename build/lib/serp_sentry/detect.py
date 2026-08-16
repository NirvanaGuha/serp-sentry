"""Pure ranking-change detection between two SERP snapshots."""


def site_position(rows: list[dict], site_domain: str) -> int | None:
    """Best (lowest) position of the site in a snapshot; None if absent.
    Matches the domain and its subdomains."""
    site = site_domain.lower().removeprefix("www.")
    positions = [r["position"] for r in rows
                 if r["domain"] == site or r["domain"].endswith("." + site)]
    return min(positions) if positions else None


def compare(old: list[dict], new: list[dict], site_domain: str,
            min_position_change: int = 3) -> list[dict]:
    """Events between two snapshots of one keyword's top-N.

    Event types:
      you_entered / you_dropped / you_moved   — your own site (always reported;
                                                 moves need >= min_position_change)
      new_entrant / dropout                    — other domains entering/leaving top-N
    """
    events = []
    site = site_domain.lower().removeprefix("www.")

    old_pos, new_pos = site_position(old, site), site_position(new, site)
    if old_pos is None and new_pos is not None:
        events.append({"type": "you_entered", "to": new_pos})
    elif old_pos is not None and new_pos is None:
        events.append({"type": "you_dropped", "from": old_pos})
    elif old_pos is not None and new_pos is not None \
            and abs(new_pos - old_pos) >= min_position_change:
        events.append({"type": "you_moved", "from": old_pos, "to": new_pos,
                       "direction": "up" if new_pos < old_pos else "down"})

    def others(rows):
        return {r["domain"] for r in rows
                if r["domain"] != site and not r["domain"].endswith("." + site)}

    old_domains, new_domains = others(old), others(new)
    for r in new:
        if r["domain"] in new_domains - old_domains:
            events.append({"type": "new_entrant", "domain": r["domain"],
                           "position": r["position"], "title": r["title"],
                           "url": r["url"]})
    for r in old:
        if r["domain"] in old_domains - new_domains:
            events.append({"type": "dropout", "domain": r["domain"],
                           "old_position": r["position"]})
    return events


def severity(events: list[dict]) -> str:
    """'high' when your own site moved; 'info' for other-domain churn."""
    return ("high" if any(e["type"].startswith("you_") for e in events)
            else "info")


def format_event(e: dict, site_domain: str) -> str:
    t = e["type"]
    if t == "you_entered":
        return f"🎉 {site_domain} ENTERED the top 10 at #{e['to']}"
    if t == "you_dropped":
        return f"🔴 {site_domain} DROPPED OUT of the top 10 (was #{e['from']})"
    if t == "you_moved":
        arrow = "▲" if e["direction"] == "up" else "▼"
        return f"{arrow} {site_domain}: #{e['from']} → #{e['to']}"
    if t == "new_entrant":
        return f"👀 new in top 10: {e['domain']} at #{e['position']} ({e['title'][:60]})"
    if t == "dropout":
        return f"· left top 10: {e['domain']} (was #{e['old_position']})"
    return str(e)
