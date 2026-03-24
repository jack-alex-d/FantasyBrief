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
    """Filter news items to only those mentioning rostered players."""
    relevant = []
    for item in news_items:
        text = (item["title"] + " " + item["summary"]).lower()
        for name in player_names:
            # Match on last name (most reliable)
            last_name = name.split()[-1].lower() if name.split() else ""
            if last_name and len(last_name) > 2 and last_name in text:
                item["matched_player"] = name
                relevant.append(item)
                break
    return relevant
