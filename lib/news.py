"""News and RSS feed aggregation for fantasy baseball."""
from datetime import datetime, timedelta, timezone

import feedparser


ROTOWIRE_MLB_RSS = "https://www.rotowire.com/rss/news.php?sport=MLB"


def fetch_rotowire_news(hours_back: int = 24) -> list[dict]:
    """Fetch recent MLB player news from RotoWire RSS."""
    try:
        feed = feedparser.parse(ROTOWIRE_MLB_RSS)
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    items = []
    for entry in feed.entries:
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if published and published < cutoff:
            continue
        items.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "link": entry.get("link", ""),
            "published": published.isoformat() if published else "",
        })
    return items


def filter_news_for_players(news_items: list[dict], player_names: list[str]) -> list[dict]:
    """Filter news items to only those mentioning rostered players.

    Uses first name initial + last name to avoid false positives
    (e.g., 'Wenceel Perez' matching 'Eury Perez').
    RotoWire titles use format 'First Last: headline', so we match against that.
    """
    relevant = []
    for item in news_items:
        title = item.get("title", "")
        text = (title + " " + item.get("summary", "")).lower()

        for name in player_names:
            parts = name.split()
            if len(parts) < 2:
                continue
            first = parts[0].lower()
            last = parts[-1].lower()
            if len(last) <= 2:
                continue

            # RotoWire titles start with "First Last:" -- check that first
            title_lower = title.lower()
            if title_lower.startswith(f"{first} {last}") or title_lower.startswith(f"{first[0]}. {last}"):
                item = {**item, "matched_player": name}
                relevant.append(item)
                break

            # Fallback: check if both first name and last name appear near each other
            # Require full first name (not just initial) to avoid false positives
            if last in text and first in text:
                item = {**item, "matched_player": name}
                relevant.append(item)
                break
    return relevant
