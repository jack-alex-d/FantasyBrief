"""Fantrax API client using saved browser cookies."""
import json
import os
from datetime import date

import requests


COOKIES_FILE = "cookies.json"
API_URL = "https://www.fantrax.com/fxpa/req"


class FantraxClient:
    def __init__(self, league_id: str):
        self.league_id = league_id
        self.session = requests.Session()
        self._load_cookies()

    def _load_cookies(self):
        if not os.path.exists(COOKIES_FILE):
            raise FileNotFoundError(
                f"No {COOKIES_FILE} found. Run auth_login.py first."
            )
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        for cookie in cookies:
            self.session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain", ".fantrax.com"),
                path=cookie.get("path", "/"),
            )

    def _request(self, methods: list[dict]) -> list[dict]:
        json_data = {
            "msgs": [
                {"method": m["method"], "data": {"leagueId": self.league_id, **m.get("data", {})}}
                for m in methods
            ]
        }
        resp = self.session.post(
            API_URL,
            params={"leagueId": self.league_id},
            json=json_data,
        )
        resp.raise_for_status()
        data = resp.json()
        if "pageError" in data and data["pageError"].get("code") == "WARNING_NOT_LOGGED_IN":
            raise PermissionError(
                "Fantrax session expired. Run auth_login.py again."
            )
        responses = data.get("responses", [])
        return [r.get("data", {}) for r in responses]

    def get_league_info(self) -> dict:
        results = self._request([{"method": "getFantasyLeagueInfo"}])
        return results[0] if results else {}

    def get_teams(self) -> dict[str, str]:
        """Return dict of team_id -> team_name."""
        info = self._get_cached_league_info()
        settings = info.get("fantasySettings", {})
        teams = {}
        fantasy_teams = info.get("fantasyTeams", settings.get("fantasyTeams", {}))
        if isinstance(fantasy_teams, dict):
            for tid, tdata in fantasy_teams.items():
                name = tdata.get("name", tdata.get("shortName", tid))
                teams[tid] = name
        if not teams and settings.get("myDefaultTeamId"):
            tid = settings["myDefaultTeamId"]
            teams[tid] = settings.get("teamName", "My Team")
        return teams

    def get_my_team_id(self) -> str | None:
        """Get the logged-in user's team ID directly from league settings."""
        info = self._get_cached_league_info()
        settings = info.get("fantasySettings", {})
        return settings.get("myDefaultTeamId")

    def find_team_id(self, team_name: str) -> str | None:
        """Find team ID by name, falling back to logged-in user's team."""
        teams = self.get_teams()
        team_name_lower = team_name.lower()
        for tid, tname in teams.items():
            if team_name_lower in tname.lower() or tname.lower() in team_name_lower:
                return tid
        return self.get_my_team_id()

    def _get_cached_league_info(self) -> dict:
        if not hasattr(self, "_league_info_cache"):
            self._league_info_cache = self.get_league_info()
        return self._league_info_cache

    def get_roster(self, team_id: str, period: int | None = None) -> list[dict]:
        """Get roster with player stats for a team."""
        results = self._request([
            {"method": "getTeamRosterInfo", "data": {"teamId": team_id, "view": "STATS"}},
        ])
        if not results:
            return []
        data = results[0]
        players = []
        for table in data.get("tables", []):
            # Get stat column names from header
            header_cells = table.get("header", {}).get("cells", [])
            stat_names = [
                h.get("shortName", f"col{i}") for i, h in enumerate(header_cells)
            ]
            sc_group = table.get("scGroup", "")
            is_pitcher_table = sc_group == "20"

            for row in table.get("rows", []):
                scorer = row.get("scorer", {})
                url_name = scorer.get("urlName", "")
                if not url_name:
                    continue  # Skip empty rows
                # Build clean player name from urlName
                name = url_name.replace("-", " ").title()
                pos_raw = scorer.get("posShortNames", "")
                # Strip HTML bold tags
                position = pos_raw.replace("<b>", "").replace("</b>", "")
                team_name = scorer.get("teamName", "")
                # Extract team abbreviation from teamName
                team_short = _team_abbrev(team_name)

                # Extract news/notes from icons
                icons = scorer.get("icons", [])
                news_notes = []
                for icon in icons:
                    tooltip = icon.get("tooltip", "")
                    if tooltip and len(tooltip) > 20:
                        news_notes.append(tooltip)

                player = {
                    "fantrax_id": scorer.get("scorerId", ""),
                    "name": name,
                    "team": team_short,
                    "team_full": team_name,
                    "position": position,
                    "status": row.get("statusId", ""),
                    "is_pitcher": is_pitcher_table,
                    "news": news_notes,
                }
                # Map cell values to stat names
                cells = row.get("cells", [])
                for i, cell in enumerate(cells):
                    stat_name = stat_names[i] if i < len(stat_names) else f"col{i}"
                    if isinstance(cell, dict):
                        player[stat_name] = cell.get("content", "")
                    else:
                        player[stat_name] = cell
                players.append(player)
        return players

    def get_live_scoring(self, scoring_date: date | None = None) -> dict:
        """Get live scoring data for a date."""
        data = {}
        if scoring_date:
            data["date"] = scoring_date.strftime("%Y-%m-%d")
        results = self._request([
            {"method": "getLiveScoringStats", "data": {**data, "newView": "true", "period": "1", "playerViewType": "1", "sppId": "-1", "viewType": "1"}},
        ])
        return results[0] if results else {}

    def get_standings(self) -> dict:
        """Get current league standings."""
        results = self._request([
            {"method": "getStandings", "data": {"view": "STANDINGS"}},
        ])
        return results[0] if results else {}

    def get_matchup_scores(self) -> dict:
        """Get current matchup/scoring period scores."""
        results = self._request([
            {"method": "getLiveScoringStats", "data": {"newView": "true"}},
        ])
        return results[0] if results else {}


# Common MLB team name -> abbreviation mapping
_TEAM_ABBREVS = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Athletics": "OAK", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
}


def _team_abbrev(team_name: str) -> str:
    return _TEAM_ABBREVS.get(team_name, team_name)
