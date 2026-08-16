"""Unit tests — synthetic data, no network."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from serp_sentry.detect import compare, format_event, severity, site_position
from serp_sentry.providers import domain_of, parse_serpapi, parse_serper


def rows(*specs):
    """('domain', pos) tuples -> snapshot rows."""
    return [{"position": p, "domain": d, "url": f"https://{d}/x", "title": f"T {d}"}
            for d, p in specs]


OLD = rows(("bigbrand.com", 1), ("example.com", 4), ("rival.com", 7), ("old.com", 9))


def test_domain_of():
    assert domain_of("https://www.example.com/page?q=1") == "example.com"
    assert domain_of("https://blog.example.com/p") == "blog.example.com"


def test_parse_serper():
    data = {"organic": [{"position": 1, "link": "https://www.a.com/x", "title": "A"},
                        {"position": 2, "link": "https://b.com/y", "title": "B"}]}
    out = parse_serper(data, 10)
    assert out[0] == {"position": 1, "domain": "a.com", "url": "https://www.a.com/x",
                      "title": "A"}
    assert len(parse_serper(data, 1)) == 1


def test_parse_serpapi():
    data = {"organic_results": [{"position": 3, "link": "https://c.com/z", "title": "C"}]}
    assert parse_serpapi(data, 10)[0]["domain"] == "c.com"


def test_site_position_matches_subdomains():
    snap = rows(("bigbrand.com", 1), ("blog.example.com", 5))
    assert site_position(snap, "example.com") == 5
    assert site_position(snap, "www.example.com") == 5
    assert site_position(snap, "missing.com") is None


def test_no_events_on_identical():
    assert compare(OLD, OLD, "example.com") == []


def test_you_moved_threshold():
    new = rows(("bigbrand.com", 1), ("example.com", 6), ("rival.com", 7), ("old.com", 9))
    assert compare(OLD, new, "example.com", min_position_change=3) == []  # 4->6 below floor
    events = compare(OLD, new, "example.com", min_position_change=2)
    assert events == [{"type": "you_moved", "from": 4, "to": 6, "direction": "down"}]


def test_you_dropped_and_new_entrant():
    new = rows(("bigbrand.com", 1), ("upstart.io", 4), ("rival.com", 7), ("old.com", 9))
    events = compare(OLD, new, "example.com")
    types = {e["type"] for e in events}
    assert "you_dropped" in types and "new_entrant" in types
    entrant = next(e for e in events if e["type"] == "new_entrant")
    assert entrant["domain"] == "upstart.io" and entrant["position"] == 4
    assert severity(events) == "high"


def test_dropout_and_info_severity():
    new = rows(("bigbrand.com", 1), ("example.com", 4), ("rival.com", 7), ("fresh.com", 9))
    events = compare(OLD, new, "example.com")
    assert {e["type"] for e in events} == {"new_entrant", "dropout"}
    assert severity(events) == "info"


def test_you_entered():
    old = rows(("bigbrand.com", 1), ("rival.com", 2))
    new = rows(("bigbrand.com", 1), ("example.com", 3))
    events = compare(old, new, "example.com")
    assert {"type": "you_entered", "to": 3} in events


def test_format_event_strings():
    assert "ENTERED" in format_event({"type": "you_entered", "to": 3}, "example.com")
    assert "#4 → #6" in format_event(
        {"type": "you_moved", "from": 4, "to": 6, "direction": "down"}, "example.com")


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
            except AssertionError as e:
                print(f"  ✗ {name}: {e}")
                failed += 1
    sys.exit(1 if failed else 0)
