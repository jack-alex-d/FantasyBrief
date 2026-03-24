"""MLB Stats API and Statcast data fetching."""
from datetime import date, timedelta

import pandas as pd
import requests
import statsapi

# Defer pybaseball import to avoid slow startup when not needed
_pybaseball_imported = False
_statcast = None
_statcast_batter = None
_statcast_pitcher = None
_playerid_lookup = None


def _import_pybaseball():
    global _pybaseball_imported, _statcast, _statcast_batter, _statcast_pitcher, _playerid_lookup
    if not _pybaseball_imported:
        from pybaseball import statcast, statcast_batter, statcast_pitcher, playerid_lookup
        from pybaseball import cache
        cache.enable()
        _statcast = statcast
        _statcast_batter = statcast_batter
        _statcast_pitcher = statcast_pitcher
        _playerid_lookup = playerid_lookup
        _pybaseball_imported = True


def get_yesterdays_games(target_date: date | None = None) -> list[dict]:
    """Get all MLB games from yesterday (or target_date)."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    date_str = target_date.strftime("%m/%d/%Y")
    games = statsapi.schedule(date=date_str)
    return [g for g in games if g.get("status") == "Final"]


def get_box_score(game_pk: int) -> dict:
    """Get box score data for a specific game."""
    return statsapi.boxscore_data(game_pk)


def get_all_player_box_scores(roster: list[dict], games: list[dict]) -> dict[str, dict]:
    """Batch lookup: scan all box scores once and return stats for matching players.

    Matches on last name + team to avoid false positives (e.g., different Dominguez).
    Accepts roster dicts with 'name' and 'team_full' keys, and pre-fetched games list.
    Returns dict of player_name -> {type, game, person_id, stats}.
    """
    results = {}

    # Build lookup: last_name -> [(roster_name, team_full), ...]
    name_lookup: dict[str, list[tuple[str, str]]] = {}
    for p in roster:
        name = p.get("name", "")
        team_full = p.get("team_full", "")
        parts = name.lower().split()
        if parts:
            last = parts[-1]
            name_lookup.setdefault(last, []).append((name, team_full.lower()))

    for game in games:
        try:
            box = get_box_score(game["game_id"])
        except Exception:
            continue
        team_info = box.get("teamInfo", {})
        # Map side -> team name for matching
        side_teams = {
            "away": team_info.get("away", {}).get("teamName", "").lower(),
            "home": team_info.get("home", {}).get("teamName", "").lower(),
        }
        game_score = f"{game.get('away_name', '')} {game.get('away_score', '?')}, {game.get('home_name', '')} {game.get('home_score', '?')}"

        for side in ["away", "home"]:
            side_team = side_teams[side]
            # Batters
            for batter in box.get(f"{side}Batters", []):
                if not isinstance(batter, dict) or batter.get("personId", 0) == 0:
                    continue
                box_name = batter.get("name", "")
                last_name = box_name.lower().split()[-1] if box_name else ""
                if last_name not in name_lookup:
                    continue
                for roster_name, roster_team in name_lookup[last_name]:
                    # Match: last name matches AND team matches
                    if roster_name in results:
                        continue
                    if roster_team and side_team and side_team not in roster_team and roster_team not in side_team:
                        continue
                    results[roster_name] = {
                        "type": "batter",
                        "game": game_score,
                        "person_id": batter.get("personId"),
                        "stats": {
                            "ab": batter.get("ab", "0"),
                            "h": batter.get("h", "0"),
                            "r": batter.get("r", "0"),
                            "doubles": batter.get("doubles", "0"),
                            "triples": batter.get("triples", "0"),
                            "hr": batter.get("hr", "0"),
                            "rbi": batter.get("rbi", "0"),
                            "bb": batter.get("bb", "0"),
                            "k": batter.get("k", "0"),
                            "sb": batter.get("sb", "0"),
                            "avg": batter.get("avg", ""),
                            "hbp": batter.get("hbp", "0"),
                        },
                    }
                    break
            # Pitchers
            for pitcher in box.get(f"{side}Pitchers", []):
                if not isinstance(pitcher, dict) or pitcher.get("personId", 0) == 0:
                    continue
                box_name = pitcher.get("name", "")
                last_name = box_name.lower().split()[-1] if box_name else ""
                if last_name not in name_lookup:
                    continue
                for roster_name, roster_team in name_lookup[last_name]:
                    if roster_name in results:
                        continue
                    if roster_team and side_team and side_team not in roster_team and roster_team not in side_team:
                        continue
                    results[roster_name] = {
                        "type": "pitcher",
                        "game": game_score,
                        "person_id": pitcher.get("personId"),
                        "stats": {
                            "ip": pitcher.get("ip", "0"),
                            "h": pitcher.get("h", "0"),
                            "r": pitcher.get("r", "0"),
                            "er": pitcher.get("er", "0"),
                            "bb": pitcher.get("bb", "0"),
                            "k": pitcher.get("k", "0"),
                            "hr": pitcher.get("hr", "0"),
                            "pitches": pitcher.get("p", "0"),
                            "strikes": pitcher.get("s", "0"),
                            "era": pitcher.get("era", ""),
                            "note": pitcher.get("note", ""),
                        },
                    }
                    break
    return results


def lookup_mlbam_id(player_name: str) -> int | None:
    """Look up a player's MLBAM ID by name."""
    results = statsapi.lookup_player(player_name)
    if results:
        return results[0]["id"]
    return None


def get_statcast_batter_day(player_name: str, target_date: date | None = None, mlbam_id: int | None = None) -> pd.DataFrame:
    """Get Statcast data for a batter on a specific date."""
    _import_pybaseball()
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    if mlbam_id is None:
        mlbam_id = lookup_mlbam_id(player_name)
    if mlbam_id is None:
        return pd.DataFrame()
    date_str = target_date.strftime("%Y-%m-%d")
    try:
        data = _statcast_batter(date_str, date_str, mlbam_id)
        return data if data is not None and not data.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_statcast_pitcher_day(player_name: str, target_date: date | None = None, mlbam_id: int | None = None) -> pd.DataFrame:
    """Get Statcast data for a pitcher on a specific date."""
    _import_pybaseball()
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    if mlbam_id is None:
        mlbam_id = lookup_mlbam_id(player_name)
    if mlbam_id is None:
        return pd.DataFrame()
    date_str = target_date.strftime("%Y-%m-%d")
    try:
        data = _statcast_pitcher(date_str, date_str, mlbam_id)
        return data if data is not None and not data.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _safe_round(val, decimals=1):
    """Round a value, returning None if NaN."""
    if pd.isna(val):
        return None
    return round(float(val), decimals)


def compute_batter_metrics(statcast_df: pd.DataFrame) -> dict:
    """Compute advanced batter metrics from Statcast pitch-level data."""
    if statcast_df.empty:
        return {}
    metrics = {}
    bbe = statcast_df[statcast_df["type"] == "X"]
    metrics["bbe_count"] = len(bbe)
    if not bbe.empty:
        metrics["avg_exit_velo"] = _safe_round(bbe["launch_speed"].mean()) if "launch_speed" in bbe.columns else None
        metrics["max_exit_velo"] = _safe_round(bbe["launch_speed"].max()) if "launch_speed" in bbe.columns else None
        metrics["avg_launch_angle"] = _safe_round(bbe["launch_angle"].mean()) if "launch_angle" in bbe.columns else None
        # Barrel: exit velo >= 98 mph and launch angle 26-30 (simplified)
        if "launch_speed" in bbe.columns and "launch_angle" in bbe.columns:
            barrels = bbe[
                (bbe["launch_speed"] >= 98) &
                (bbe["launch_angle"] >= 26) &
                (bbe["launch_angle"] <= 30)
            ]
            metrics["barrels"] = len(barrels)
            metrics["barrel_pct"] = _safe_round(len(barrels) / len(bbe) * 100)
        # Hard hit (>= 95 mph)
        if "launch_speed" in bbe.columns:
            hard_hit = bbe[bbe["launch_speed"] >= 95]
            metrics["hard_hit_pct"] = _safe_round(len(hard_hit) / len(bbe) * 100)
        # xBA and expected hits
        if "estimated_ba_using_speedangle" in bbe.columns:
            xba_values = bbe["estimated_ba_using_speedangle"].dropna()
            metrics["xBA"] = _safe_round(xba_values.mean(), 3)
            if len(xba_values) > 0:
                expected_hits = float(xba_values.sum())
                actual_hits = len(bbe[bbe["events"].isin([
                    "single", "double", "triple", "home_run",
                ])] if "events" in bbe.columns else [])
                metrics["expected_hits"] = round(expected_hits, 1)
                metrics["actual_hits"] = actual_hits
                metrics["hit_luck"] = round(actual_hits - expected_hits, 1)
        # xwOBA -> expected fantasy points per BBE
        # Uses both xBA and xwOBA: xwOBA/xBA gives average hit quality on wOBA scale,
        # then we map wOBA scale to fantasy scale using a linear fit through:
        #   1B: wOBA=0.883 -> FP=1, 2B: wOBA=1.244 -> FP=2,
        #   3B: wOBA=1.569 -> FP=3, HR: wOBA=2.065 -> FP=4
        # Fit: FP_per_hit = 2.560 * avg_wOBA_per_hit - 1.188
        # Then: xFP_per_BBE = xBA * FP_per_hit (expected hits * expected value per hit)
        WOBA_TO_FP_SLOPE = 2.560
        WOBA_TO_FP_INTERCEPT = -1.188
        if "estimated_woba_using_speedangle" in bbe.columns:
            # Need per-BBE pairs of xBA and xwOBA
            bbe_with_both = bbe[["estimated_ba_using_speedangle", "estimated_woba_using_speedangle"]].dropna()
            if len(bbe_with_both) > 0:
                xwoba_all = bbe["estimated_woba_using_speedangle"].dropna()
                metrics["xwOBA"] = _safe_round(xwoba_all.mean(), 3)
                xfp_total = 0.0
                for _, pair in bbe_with_both.iterrows():
                    per_xba = pair["estimated_ba_using_speedangle"]
                    per_xwoba = pair["estimated_woba_using_speedangle"]
                    if per_xba > 0.001:
                        avg_woba_per_hit = per_xwoba / per_xba
                        fp_per_hit = max(0, WOBA_TO_FP_SLOPE * avg_woba_per_hit + WOBA_TO_FP_INTERCEPT)
                        xfp_total += per_xba * fp_per_hit
                    # else: near-zero xBA means almost certain out, contributes ~0 xFP
                metrics["xwoba_fantasy_pts"] = round(xfp_total, 1)
            elif "estimated_woba_using_speedangle" in bbe.columns:
                xwoba_all = bbe["estimated_woba_using_speedangle"].dropna()
                if len(xwoba_all) > 0:
                    metrics["xwOBA"] = _safe_round(xwoba_all.mean(), 3)
    # Plate discipline
    total_pitches = len(statcast_df)
    swings = statcast_df[statcast_df["description"].str.contains("swing|foul|hit_into_play", case=False, na=False)]
    whiffs = statcast_df[statcast_df["description"].str.contains("swinging_strike|foul_tip", case=False, na=False)]
    # Zone info
    if "zone" in statcast_df.columns:
        in_zone = statcast_df[statcast_df["zone"].between(1, 9)]
        out_zone = statcast_df[~statcast_df["zone"].between(1, 9)]
        if len(out_zone) > 0:
            chases = out_zone[out_zone["description"].str.contains("swing|foul|hit_into_play", case=False, na=False)]
            metrics["chase_rate"] = round(len(chases) / len(out_zone) * 100, 1)
    if len(swings) > 0:
        metrics["whiff_rate"] = round(len(whiffs) / len(swings) * 100, 1)
    metrics["pitches_seen"] = total_pitches
    return metrics


def compute_pitcher_metrics(statcast_df: pd.DataFrame) -> dict:
    """Compute advanced pitcher metrics from Statcast pitch-level data."""
    if statcast_df.empty:
        return {}
    metrics = {}
    total_pitches = len(statcast_df)
    metrics["total_pitches"] = total_pitches
    # Whiff rate
    swings = statcast_df[statcast_df["description"].str.contains("swing|foul|hit_into_play", case=False, na=False)]
    whiffs = statcast_df[statcast_df["description"].str.contains("swinging_strike|foul_tip", case=False, na=False)]
    if len(swings) > 0:
        metrics["whiff_rate"] = round(len(whiffs) / len(swings) * 100, 1)
    # CSW% (called strikes + whiffs / total pitches)
    called_strikes = statcast_df[statcast_df["description"].str.contains("called_strike", case=False, na=False)]
    csw = len(called_strikes) + len(whiffs)
    metrics["csw_pct"] = round(csw / total_pitches * 100, 1)
    # Chase rate
    if "zone" in statcast_df.columns:
        out_zone = statcast_df[~statcast_df["zone"].between(1, 9)]
        if len(out_zone) > 0:
            chases = out_zone[out_zone["description"].str.contains("swing|foul|hit_into_play", case=False, na=False)]
            metrics["chase_rate"] = round(len(chases) / len(out_zone) * 100, 1)
    # Batted ball quality against
    bbe = statcast_df[statcast_df["type"] == "X"]
    if not bbe.empty:
        if "launch_speed" in bbe.columns:
            metrics["avg_exit_velo_against"] = _safe_round(bbe["launch_speed"].mean())
            hard_hit = bbe[bbe["launch_speed"] >= 95]
            metrics["hard_hit_pct_against"] = _safe_round(len(hard_hit) / len(bbe) * 100)
        if "estimated_ba_using_speedangle" in bbe.columns:
            metrics["xBA_against"] = _safe_round(bbe["estimated_ba_using_speedangle"].mean(), 3)
    # Pitch mix
    if "pitch_type" in statcast_df.columns:
        pitch_counts = statcast_df["pitch_type"].value_counts()
        metrics["pitch_mix"] = {
            pt: round(count / total_pitches * 100, 1)
            for pt, count in pitch_counts.items()
            if pd.notna(pt)
        }
    return metrics


_MILB_SPORT_IDS = "11,12,13,14,16"
_SPORT_LEVEL_NAMES = {11: "AAA", 12: "AA", 13: "A+", 14: "A", 16: "Rookie/Complex"}


def _resolve_mlbam_id(player_name: str) -> int | None:
    """Resolve a player name to MLBAM ID via people search (finds MiLB prospects)."""
    try:
        resp = requests.get(
            "https://statsapi.mlb.com/api/v1/people/search",
            params={"names": player_name, "sportIds": f"1,{_MILB_SPORT_IDS}"},
            timeout=10,
        )
        results = resp.json().get("searchResults", [])
        if results:
            person = results[0].get("person", results[0])
            return person.get("id")
    except Exception:
        pass
    return None


def _fetch_milb_game_log(player_name: str, mlbam_id: int, target_date: date) -> dict | None:
    """Fetch a player's MiLB game log for target_date. Returns stat dict or None."""
    date_str = target_date.strftime("%Y-%m-%d")
    season = target_date.year

    for group in ["hitting", "pitching"]:
        for sport_id in [11, 12, 13, 14, 16]:
            try:
                resp = requests.get(
                    f"https://statsapi.mlb.com/api/v1/people/{mlbam_id}/stats",
                    params={"stats": "gameLog", "season": season, "group": group, "sportId": sport_id},
                    timeout=10,
                )
                for stat_group in resp.json().get("stats", []):
                    for split in stat_group.get("splits", []):
                        if split.get("date") == date_str:
                            s = split.get("stat", {})
                            team = split.get("team", {})
                            opponent = split.get("opponent", {})
                            level = _SPORT_LEVEL_NAMES.get(sport_id, "MiLB")
                            is_home = split.get("isHome", False)
                            if is_home:
                                game_str = f"{opponent.get('name', '?')} @ {team.get('name', '?')}"
                            else:
                                game_str = f"{team.get('name', '?')} @ {opponent.get('name', '?')}"

                            if group == "hitting":
                                return {
                                    "type": "batter",
                                    "level": level,
                                    "game": game_str,
                                    "stats": {
                                        "ab": str(s.get("atBats", 0)),
                                        "h": str(s.get("hits", 0)),
                                        "r": str(s.get("runs", 0)),
                                        "doubles": str(s.get("doubles", 0)),
                                        "triples": str(s.get("triples", 0)),
                                        "hr": str(s.get("homeRuns", 0)),
                                        "rbi": str(s.get("rbi", 0)),
                                        "bb": str(s.get("baseOnBalls", 0)),
                                        "k": str(s.get("strikeOuts", 0)),
                                        "sb": str(s.get("stolenBases", 0)),
                                        "hbp": str(s.get("hitByPitch", 0)),
                                        "summary": s.get("summary", ""),
                                    },
                                }
                            else:
                                return {
                                    "type": "pitcher",
                                    "level": level,
                                    "game": game_str,
                                    "stats": {
                                        "ip": str(s.get("inningsPitched", "0")),
                                        "h": str(s.get("hits", 0)),
                                        "r": str(s.get("runs", 0)),
                                        "er": str(s.get("earnedRuns", 0)),
                                        "bb": str(s.get("baseOnBalls", 0)),
                                        "k": str(s.get("strikeOuts", 0)),
                                        "hr": str(s.get("homeRuns", 0)),
                                        "pitches": str(s.get("numberOfPitches", 0)),
                                        "strikes": str(s.get("strikes", 0)),
                                        "note": s.get("note", ""),
                                        "summary": s.get("summary", ""),
                                    },
                                }
            except Exception:
                continue
    return None


def get_milb_player_stats_batch(
    roster: list[dict],
    player_names: list[str],
    target_date: date | None = None,
) -> dict[str, dict]:
    """Player-first MiLB stats lookup across all levels.

    For each DNP player: resolve MLBAM ID via people search, then check their
    game log for the target date. No box score scanning needed.
    All levels covered: AAA, AA, A+, A, Rookie/Complex/DSL.
    Parallelized for speed.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    if not player_names:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _lookup_player(name: str) -> tuple[str, dict | None]:
        # First try people search (finds MiLB prospects)
        mlbam_id = _resolve_mlbam_id(name)
        if not mlbam_id:
            # Fallback: try statsapi.lookup_player
            mlbam_id = lookup_mlbam_id(name)
        if not mlbam_id:
            return name, None
        result = _fetch_milb_game_log(name, mlbam_id, target_date)
        return name, result

    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_lookup_player, name): name for name in player_names}
        for future in as_completed(futures):
            try:
                name, data = future.result(timeout=30)
                if data:
                    results[name] = data
            except Exception:
                continue
    return results


def get_todays_probable_pitchers(target_date: date | None = None) -> list[dict]:
    """Get today's probable pitchers."""
    if target_date is None:
        target_date = date.today()
    date_str = target_date.strftime("%m/%d/%Y")
    games = statsapi.schedule(date=date_str)
    matchups = []
    for game in games:
        matchup = {
            "away_team": game.get("away_name", ""),
            "home_team": game.get("home_name", ""),
            "away_pitcher": game.get("away_probable_pitcher", "TBD"),
            "home_pitcher": game.get("home_probable_pitcher", "TBD"),
            "game_time": game.get("game_datetime", ""),
        }
        matchups.append(matchup)
    return matchups


def get_transactions(target_date: date | None = None) -> list[dict]:
    """Get MLB transactions for a date."""
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    date_str = target_date.strftime("%m/%d/%Y")
    try:
        resp = requests.get(
            "https://statsapi.mlb.com/api/v1/transactions",
            params={"startDate": date_str, "endDate": date_str},
        )
        data = resp.json()
        transactions = []
        for tx in data.get("transactions", []):
            transactions.append({
                "player": tx.get("person", {}).get("fullName", "Unknown"),
                "team": tx.get("toTeam", tx.get("fromTeam", {})).get("name", ""),
                "type": tx.get("typeDesc", ""),
                "description": tx.get("description", ""),
            })
        return transactions
    except Exception:
        return []


def _name_match(query: str, candidate: str) -> bool:
    """Fuzzy name matching -- checks if last name matches."""
    query_parts = query.lower().split()
    candidate_parts = candidate.lower().split()
    if not query_parts or not candidate_parts:
        return False
    # Last name match
    if query_parts[-1] == candidate_parts[-1]:
        return True
    # Full name match
    if query.lower() == candidate.lower():
        return True
    return False
