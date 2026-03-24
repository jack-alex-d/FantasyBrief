"""News and RSS feed aggregation for fantasy baseball."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

import feedparser


ROTOWIRE_MLB_RSS = "https://www.rotowire.com/rss/news.php?sport=MLB"
COOKIES_FILE = "cookies.json"


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
            last_name = name.split()[-1].lower() if name.split() else ""
            if last_name and len(last_name) > 2 and last_name in text:
                item["matched_player"] = name
                relevant.append(item)
                break
    return relevant


def fetch_fantrax_full_news(roster: list[dict], league_id: str) -> dict[str, list[dict]]:
    """Fetch full player news from Fantrax player card pages via Playwright.

    Returns dict of player_name -> list of {headline, text, date} news items.
    Only fetches for players whose tooltips indicate recent news.
    """
    if not os.path.exists(COOKIES_FILE):
        return {}

    # Collect player IDs that have news tooltips
    players_with_news = []
    for p in roster:
        fantrax_id = p.get("fantrax_id", "")
        name = p.get("name", "")
        news = p.get("news", [])
        if fantrax_id and news:
            players_with_news.append((name, fantrax_id))

    if not players_with_news:
        return {}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}

    results = {}
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

            # Load cookies
            pw_cookies = []
            for c in cookies:
                cookie = {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".fantrax.com"),
                    "path": c.get("path", "/"),
                }
                if c.get("expires", 0) > 0:
                    cookie["expires"] = c["expires"]
                pw_cookies.append(cookie)
            context.add_cookies(pw_cookies)

            page = context.new_page()

            for name, scorer_id in players_with_news:
                try:
                    url = f"https://www.fantrax.com/fantasy/league/{league_id}/players;statusOrTeamFilter=ALL;scorerIdTo498={scorer_id}"
                    page.goto(url, wait_until="domcontentloaded", timeout=10000)
                    # Wait for the player card news to render
                    page.wait_for_timeout(2000)

                    # Extract news items from the player card
                    news_items = page.evaluate("""() => {
                        const items = [];
                        // Look for news update elements in the player card
                        const newsEls = document.querySelectorAll('.news-update, .player-news-item, [class*="news"]');
                        for (const el of newsEls) {
                            const text = el.innerText.trim();
                            if (text.length > 20) {
                                items.push(text);
                            }
                        }
                        // Also try the specific Fantrax player card news section
                        const cardNews = document.querySelectorAll('.scorer-card-news-item, .player-card__news-item');
                        for (const el of cardNews) {
                            const text = el.innerText.trim();
                            if (text.length > 20) {
                                items.push(text);
                            }
                        }
                        return items;
                    }""")

                    if news_items:
                        results[name] = [{"text": item} for item in news_items[:3]]
                except Exception:
                    continue

            browser.close()
    except Exception:
        pass

    return results
