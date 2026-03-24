"""HTML email formatter for the daily brief."""
from datetime import date


# Statcast metric thresholds for color coding
# (metric_key, good_direction, elite_threshold, poor_threshold)
_BATTER_THRESHOLDS = {
    "avg_exit_velo": ("high", 95, 85),
    "max_exit_velo": ("high", 105, 90),
    "xBA": ("high", 0.350, 0.200),
    "hard_hit_pct": ("high", 50, 25),
    "barrel_pct": ("high", 10, 0),
    "chase_rate": ("low", 20, 35),
    "whiff_rate": ("low", 20, 35),
}

_PITCHER_THRESHOLDS = {
    "whiff_rate": ("high", 30, 18),
    "csw_pct": ("high", 30, 22),
    "chase_rate": ("high", 35, 20),
    "avg_exit_velo_against": ("low", 85, 92),
    "hard_hit_pct_against": ("low", 25, 40),
}


def brief_to_html(
    team_name: str,
    roster: list[dict],
    box_scores: dict[str, dict],
    batter_statcast: dict[str, dict],
    pitcher_statcast: dict[str, dict],
    milb_stats: dict[str, dict],
    news_items: list[dict],
    transactions: list[dict],
    probable_pitchers: list[dict],
    target_date: date,
    fantrax_news: list[tuple[str, str]] | None = None,
    injury_flags: list[tuple[str, str]] | None = None,
) -> str:
    """Build an HTML email version of the daily brief."""
    fantrax_news = fantrax_news or []
    injury_flags = injury_flags or []

    sections = []
    sections.append(_html_header(team_name, target_date))
    sections.append(_html_hitters(roster, box_scores, batter_statcast))
    sections.append(_html_pitchers(roster, box_scores, pitcher_statcast))
    sections.append(_html_milb(roster, box_scores, milb_stats))
    sections.append(_html_news(news_items, fantrax_news, injury_flags))
    sections.append(_html_transactions(transactions, roster))
    sections.append(_html_matchups(probable_pitchers, roster))
    sections.append(_html_footer())

    body = "\n".join(s for s in sections if s)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0; color: #1a1a1a; }}
  .container {{ max-width: 640px; margin: 0 auto; background: #ffffff; }}
  .header {{ background: #1a3a5c; color: white; padding: 24px; text-align: center; }}
  .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
  .header .date {{ color: #a0c4e8; font-size: 14px; margin-top: 4px; }}
  .section {{ padding: 16px 20px; }}
  .section-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #1a3a5c; border-bottom: 2px solid #1a3a5c; padding-bottom: 6px; margin-bottom: 12px; }}
  .player {{ margin-bottom: 16px; }}
  .player-name {{ font-weight: 600; font-size: 15px; color: #1a1a1a; }}
  .player-meta {{ color: #666; font-size: 13px; }}
  .stat-line {{ font-size: 14px; font-weight: 500; margin: 4px 0; padding: 6px 10px; background: #f8f9fa; border-radius: 4px; font-family: 'SF Mono', 'Fira Code', monospace; }}
  .statcast {{ font-size: 12px; color: #555; margin: 4px 0 0 0; line-height: 1.6; }}
  .statcast .label {{ color: #888; }}
  .metric {{ display: inline-block; margin-right: 12px; white-space: nowrap; }}
  .elite {{ color: #16a34a; font-weight: 600; }}
  .good {{ color: #22863a; }}
  .poor {{ color: #cf222e; }}
  .neutral {{ color: #555; }}
  .dnp {{ color: #999; font-size: 13px; margin-top: 8px; line-height: 1.5; }}
  .dnp-label {{ font-weight: 600; color: #888; }}
  .news-item {{ margin-bottom: 10px; font-size: 14px; line-height: 1.5; }}
  .news-player {{ font-weight: 600; color: #1a3a5c; }}
  .news-text {{ color: #444; }}
  .injury {{ background: #fff3cd; border-left: 3px solid #ffc107; padding: 8px 12px; margin-bottom: 6px; font-size: 13px; border-radius: 2px; }}
  .injury-name {{ font-weight: 600; }}
  .matchup {{ font-size: 14px; margin-bottom: 8px; }}
  .matchup-teams {{ font-weight: 600; }}
  .matchup-pitchers {{ color: #666; font-size: 13px; }}
  .pitch-mix {{ font-size: 12px; color: #666; margin-top: 2px; }}
  .footer {{ background: #f8f9fa; padding: 16px; text-align: center; font-size: 12px; color: #999; }}
  .divider {{ border: 0; border-top: 1px solid #eee; margin: 0; }}
</style>
</head>
<body>
<div class="container">
{body}
</div>
</body>
</html>"""


def _html_header(team_name: str, target_date: date) -> str:
    return f"""<div class="header">
  <h1>{_esc(team_name)} -- Daily Brief</h1>
  <div class="date">{target_date.strftime('%A, %B %d, %Y')}</div>
</div>"""


def _html_hitters(roster: list[dict], box_scores: dict, statcast: dict) -> str:
    hitters = [p for p in roster if not p.get("is_pitcher", False)]
    played = [p for p in hitters if p.get("name") in box_scores]
    dnp = [p for p in hitters if p.get("name") not in box_scores]

    if not played and not dnp:
        return ""

    items = []
    for p in played:
        name = p.get("name", "")
        box = box_scores.get(name, {})
        stats = box.get("stats", {})
        game = box.get("game", "")
        metrics = statcast.get(name, {})

        stat_line = _format_batter_line(stats)
        items.append(f"""<div class="player">
  <span class="player-name">{_esc(name)}</span>
  <span class="player-meta">({_esc(p.get('position',''))}, {_esc(p.get('team',''))}) -- {_esc(game)}</span>
  <div class="stat-line">{_esc(stat_line)}</div>
  {_html_batter_statcast(metrics)}
</div>""")

    dnp_html = ""
    if dnp:
        names = ", ".join(p.get("name", "?") for p in dnp)
        dnp_html = f'<div class="dnp"><span class="dnp-label">DNP:</span> {_esc(names)}</div>'

    return f"""<div class="section">
  <div class="section-title">Hitter Highlights</div>
  {"".join(items)}
  {dnp_html}
</div>
<hr class="divider">"""


def _html_batter_statcast(metrics: dict) -> str:
    if not metrics:
        return ""
    parts = []
    bbe = metrics.get("bbe_count", 0)
    if bbe:
        parts.append(f'<span class="metric neutral">{bbe} BBE</span>')
    for key, label in [("avg_exit_velo", "EV"), ("max_exit_velo", "Max EV"), ("xBA", "xBA")]:
        val = metrics.get(key)
        if val is not None:
            unit = " mph" if "velo" in key else ""
            css = _metric_class(key, val, _BATTER_THRESHOLDS)
            parts.append(f'<span class="metric {css}">{label}: {val}{unit}</span>')
    line1 = "".join(parts)

    parts2 = []
    for key, label in [("hard_hit_pct", "HardHit%"), ("barrels", "Barrel"), ("chase_rate", "Chase%"), ("whiff_rate", "Whiff%")]:
        val = metrics.get(key)
        if val is not None:
            pct = "%" if "pct" in key or "rate" in key else ""
            css = _metric_class(key, val, _BATTER_THRESHOLDS)
            parts2.append(f'<span class="metric {css}">{label}: {val}{pct}</span>')
    line2 = "".join(parts2)

    if not line1 and not line2:
        return ""
    return f'<div class="statcast">{line1}</div><div class="statcast">{line2}</div>'


def _html_pitchers(roster: list[dict], box_scores: dict, statcast: dict) -> str:
    pitchers = [p for p in roster if p.get("is_pitcher", False)]
    played = [p for p in pitchers if p.get("name") in box_scores]
    dnp = [p for p in pitchers if p.get("name") not in box_scores]

    if not played and not dnp:
        return ""

    items = []
    for p in played:
        name = p.get("name", "")
        box = box_scores.get(name, {})
        stats = box.get("stats", {})
        game = box.get("game", "")
        note = stats.get("note", "")
        metrics = statcast.get(name, {})

        pitch_line = _format_pitcher_line(stats)
        decision = f" {_esc(note)}" if note else ""
        items.append(f"""<div class="player">
  <span class="player-name">{_esc(name)}</span>{decision}
  <span class="player-meta">({_esc(p.get('position',''))}, {_esc(p.get('team',''))}) -- {_esc(game)}</span>
  <div class="stat-line">{_esc(pitch_line)}</div>
  {_html_pitcher_statcast(metrics)}
</div>""")

    dnp_html = ""
    if dnp:
        names = ", ".join(p.get("name", "?") for p in dnp)
        dnp_html = f'<div class="dnp"><span class="dnp-label">DNP:</span> {_esc(names)}</div>'

    return f"""<div class="section">
  <div class="section-title">Pitcher Highlights</div>
  {"".join(items)}
  {dnp_html}
</div>
<hr class="divider">"""


def _html_pitcher_statcast(metrics: dict) -> str:
    if not metrics:
        return ""
    parts = []
    for key, label in [("whiff_rate", "Whiff%"), ("csw_pct", "CSW%"), ("chase_rate", "Chase%")]:
        val = metrics.get(key)
        if val is not None:
            css = _metric_class(key, val, _PITCHER_THRESHOLDS)
            parts.append(f'<span class="metric {css}">{label}: {val}%</span>')
    line1 = "".join(parts)

    parts2 = []
    for key, label in [("avg_exit_velo_against", "EV Against"), ("hard_hit_pct_against", "HardHit%"), ("xBA_against", "xBA Against")]:
        val = metrics.get(key)
        if val is not None:
            unit = " mph" if "velo" in key else ("%" if "pct" in key else "")
            css = _metric_class(key, val, _PITCHER_THRESHOLDS)
            parts2.append(f'<span class="metric {css}">{label}: {val}{unit}</span>')
    line2 = "".join(parts2)

    mix_html = ""
    pitch_mix = metrics.get("pitch_mix", {})
    if pitch_mix:
        mix_str = ", ".join(f"{pt}: {pct}%" for pt, pct in sorted(pitch_mix.items(), key=lambda x: -x[1]))
        mix_html = f'<div class="pitch-mix">Mix: {_esc(mix_str)}</div>'

    if not line1 and not line2:
        return ""
    return f'<div class="statcast">{line1}</div><div class="statcast">{line2}</div>{mix_html}'


def _html_milb(roster: list[dict], box_scores: dict, milb_stats: dict) -> str:
    milb_players = [
        p for p in roster
        if p.get("name") not in box_scores and p.get("name") in milb_stats
    ]
    if not milb_players:
        return ""

    items = []
    for p in milb_players:
        name = p.get("name", "")
        m = milb_stats.get(name, {})
        level = m.get("level", "MiLB")
        game = m.get("game", "")
        stats = m.get("stats", {})
        stat_line = stats.get("batting", stats.get("pitching", stats.get("summary", "")))
        items.append(f"""<div class="player">
  <span class="player-name">{_esc(name)}</span>
  <span class="player-meta">({_esc(p.get('position',''))}, {_esc(p.get('team',''))}) [{level}] -- {_esc(game)}</span>
  {f'<div class="stat-line">{_esc(stat_line)}</div>' if stat_line else ''}
</div>""")

    return f"""<div class="section">
  <div class="section-title">Minor League Report</div>
  {"".join(items)}
</div>
<hr class="divider">"""


def _html_news(news_items: list[dict], fantrax_news: list[tuple], injury_flags: list[tuple]) -> str:
    items_html = []

    for item in news_items[:15]:
        player = item.get("matched_player", "")
        title = item["title"]
        summary = item.get("summary", "").split("Visit RotoWire.com")[0].strip()
        items_html.append(f"""<div class="news-item">
  <span class="news-player">{_esc(player)}</span>: {_esc(title)}
  {f'<div class="news-text">{_esc(summary)}</div>' if summary else ''}
</div>""")

    for name, note in fantrax_news:
        items_html.append(f"""<div class="news-item">
  <span class="news-player">{_esc(name)}</span>: <span class="news-text">{_esc(note)}</span>
</div>""")

    injury_html = ""
    if injury_flags:
        injury_items = "".join(
            f'<div class="injury"><span class="injury-name">{_esc(name)}</span> -- {_esc(note)}</div>'
            for name, note in injury_flags
        )
        injury_html = f'<div style="margin-top: 12px;">{injury_items}</div>'

    if not items_html and not injury_html:
        return ""

    return f"""<div class="section">
  <div class="section-title">News &amp; Updates</div>
  {"".join(items_html)}
  {injury_html}
</div>
<hr class="divider">"""


def _html_transactions(transactions: list[dict], roster: list[dict]) -> str:
    roster_keys = set()
    for p in roster:
        name = p.get("name", "")
        if name:
            parts = name.lower().split()
            if len(parts) >= 2:
                roster_keys.add((parts[0][0], parts[-1]))

    relevant = []
    for tx in transactions:
        tx_player = tx.get("player", "").lower()
        tx_parts = tx_player.split()
        if len(tx_parts) >= 2 and (tx_parts[0][0], tx_parts[-1]) in roster_keys:
            relevant.append(tx)

    if not relevant:
        return ""

    items = "".join(
        f'<div class="news-item"><span class="news-player">{_esc(tx["player"])}</span> ({_esc(tx["team"])}): {_esc(tx["type"])}</div>'
        for tx in relevant[:10]
    )
    return f"""<div class="section">
  <div class="section-title">Transactions</div>
  {items}
</div>
<hr class="divider">"""


def _html_matchups(probable_pitchers: list[dict], roster: list[dict]) -> str:
    roster_teams = {p.get("team", "").upper() for p in roster if p.get("team")}

    relevant = []
    for game in probable_pitchers:
        away = game["away_team"]
        home = game["home_team"]
        for team_abbr in roster_teams:
            if team_abbr and (team_abbr in away.upper() or team_abbr in home.upper()):
                relevant.append(game)
                break

    if not relevant:
        return ""

    items = "".join(
        f"""<div class="matchup">
  <div class="matchup-teams">{_esc(g['away_team'])} @ {_esc(g['home_team'])}</div>
  <div class="matchup-pitchers">{_esc(g['away_pitcher'])} vs {_esc(g['home_pitcher'])}</div>
</div>"""
        for g in relevant
    )
    return f"""<div class="section">
  <div class="section-title">Today's Matchups</div>
  {items}
</div>"""


def _html_footer() -> str:
    return '<div class="footer">Generated by FantasyBrief</div>'


def _format_batter_line(stats: dict) -> str:
    h = int(stats.get("h", 0))
    ab = int(stats.get("ab", 0))
    parts = [f"{h}-for-{ab}"]
    for val, label in [
        (int(stats.get("doubles", 0)), "2B"), (int(stats.get("triples", 0)), "3B"),
        (int(stats.get("hr", 0)), "HR"), (int(stats.get("rbi", 0)), "RBI"),
        (int(stats.get("r", 0)), "R"), (int(stats.get("bb", 0)), "BB"),
        (int(stats.get("hbp", 0)), "HBP"), (int(stats.get("k", 0)), "K"),
        (int(stats.get("sb", 0)), "SB"),
    ]:
        if val:
            parts.append(f"{val} {label}" if val > 1 else label)
    return ", ".join(parts)


def _format_pitcher_line(stats: dict) -> str:
    ip = stats.get("ip", "0")
    h = stats.get("h", "0")
    er = stats.get("er", "0")
    bb = stats.get("bb", "0")
    k = stats.get("k", "0")
    pitches = stats.get("pitches", "0")
    strikes = stats.get("strikes", "0")
    hr = int(stats.get("hr", "0"))
    pitch_info = f"({pitches}P, {strikes}S)" if int(pitches) > 0 else ""
    hr_part = f", {hr} HR" if hr > 0 else ""
    return f"{ip} IP, {h} H, {er} ER, {bb} BB, {k} K{hr_part} {pitch_info}".strip()


def _metric_class(key: str, val: float, thresholds: dict) -> str:
    if key not in thresholds:
        return "neutral"
    direction, elite_thresh, poor_thresh = thresholds[key]
    try:
        val = float(val)
    except (TypeError, ValueError):
        return "neutral"
    if direction == "high":
        if val >= elite_thresh:
            return "elite"
        if val <= poor_thresh:
            return "poor"
    else:
        if val <= elite_thresh:
            return "elite"
        if val >= poor_thresh:
            return "poor"
    return "good"


def _esc(text: str) -> str:
    """HTML-escape text."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
