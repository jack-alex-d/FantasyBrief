"""Shared utilities used by both text and HTML brief formatters."""

_PITCHER_POSITIONS = {"SP", "RP", "P", "CL"}


def is_hitter(player: dict) -> bool:
    if "is_pitcher" in player:
        return not player["is_pitcher"]
    pos = player.get("position", "").upper()
    if not pos:
        return True
    return not any(p in _PITCHER_POSITIONS for p in pos.split(","))


def is_pitcher(player: dict) -> bool:
    if "is_pitcher" in player:
        return player["is_pitcher"]
    pos = player.get("position", "").upper()
    return any(p in _PITCHER_POSITIONS for p in pos.split(","))


def batter_sort_score(box: dict) -> float:
    """Fantasy point estimate for sorting hitters using league scoring.

    Scoring: 1B=1, 2B=2, 3B=3, HR=4, RBI=1, R=1, BB=1, HBP=1,
    SB=2, CS=-1, SO=-0.5, GIDP=-0.5, E=-0.5
    """
    s = box.get("stats", {})
    try:
        h = int(s.get("h", 0))
        doubles = int(s.get("doubles", 0))
        triples = int(s.get("triples", 0))
        hr = int(s.get("hr", 0))
        singles = h - doubles - triples - hr
        return (
            singles * 1.0
            + doubles * 2.0
            + triples * 3.0
            + hr * 4.0
            + int(s.get("rbi", 0)) * 1.0
            + int(s.get("r", 0)) * 1.0
            + int(s.get("bb", 0)) * 1.0
            + int(s.get("hbp", 0)) * 1.0
            + int(s.get("sb", 0)) * 2.0
            - int(s.get("k", 0)) * 0.5
        )
    except (ValueError, TypeError):
        return 0


def pitcher_sort_score(box: dict) -> float:
    """Fantasy point estimate for sorting pitchers using league scoring.

    Scoring: IP=3, K=1, W=3, QS=2, SV=4, HLD=1, IRS=1,
    ER=-2, H=-1, BB=-1, L=-3, BS=-1, HB=-1, BK=-0.5
    """
    s = box.get("stats", {})
    try:
        ip = float(s.get("ip", 0))
        note = s.get("note", "")
        return (
            ip * 3.0
            + int(s.get("k", 0)) * 1.0
            - int(s.get("er", 0)) * 2.0
            - int(s.get("h", 0)) * 1.0
            - int(s.get("bb", 0)) * 1.0
            + (3.0 if "W" in note else 0)
            - (3.0 if "L" in note else 0)
        )
    except (ValueError, TypeError):
        return 0


def batter_expected_pts(actual_pts: float, statcast_metrics: dict) -> float | None:
    """Compute expected fantasy points using xwOBA (or xBA fallback).

    Uses per-BBE expected weighted on-base average to estimate what the
    batted ball outcomes "should have" been worth in fantasy points.
    xwOBA captures both hit probability AND extra-base hit quality
    (exit velo + launch angle -> expected total bases).

    Conversion: xwOBA -> expected fantasy points per BBE using a linear
    mapping calibrated to our scoring (1B=1, 2B=2, 3B=3, HR=4).

    Returns None if Statcast data is insufficient.
    """
    xwoba_pts = statcast_metrics.get("xwoba_fantasy_pts")
    if xwoba_pts is not None:
        # xwoba_fantasy_pts is the sum of per-BBE expected fantasy point values
        # Add back non-contact points (BB, K, HBP, SB etc) from actual
        non_contact_pts = statcast_metrics.get("non_contact_pts", 0)
        return round(xwoba_pts + non_contact_pts, 1)

    # Fallback to xBA-only if xwOBA wasn't available
    hit_luck = statcast_metrics.get("hit_luck")
    if hit_luck is None:
        return None
    return round(actual_pts - hit_luck * 1.0, 1)


def format_batter_line(stats: dict) -> str:
    """Format traditional batter stat line: 2-for-4, HR, 2 RBI, R, BB, K"""
    h = int(stats.get("h", 0))
    ab = int(stats.get("ab", 0))
    parts = [f"{h}-for-{ab}"]
    for val, label in [
        (int(stats.get("doubles", 0)), "2B"),
        (int(stats.get("triples", 0)), "3B"),
        (int(stats.get("hr", 0)), "HR"),
        (int(stats.get("rbi", 0)), "RBI"),
        (int(stats.get("r", 0)), "R"),
        (int(stats.get("bb", 0)), "BB"),
        (int(stats.get("hbp", 0)), "HBP"),
        (int(stats.get("k", 0)), "K"),
        (int(stats.get("sb", 0)), "SB"),
    ]:
        if val:
            parts.append(f"{val} {label}" if val > 1 else label)
    return ", ".join(parts)


def format_pitcher_line(stats: dict) -> str:
    """Format traditional pitcher line: 6.0 IP, 4 H, 2 ER, 1 BB, 9 K (92 pitches)"""
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
