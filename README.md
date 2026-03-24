# FantasyBrief

Daily fantasy baseball briefs for your Fantrax league, powered by MLB Statcast data.

Get a morning report of how your team played yesterday -- traditional box score lines paired with advanced Statcast metrics, player news, injury updates, and today's matchup previews.

## Sample Output

```
  Roman Anthony (OF, BOS) -- Minnesota Twins 9, Boston Red Sox 6
    2-for-4, R, K
    Statcast: 3 BBE | Avg EV: 91.8 mph | Max EV: 103.5 | xBA: .415
             HardHit%: 33.3% | Barrel: 0 | Chase%: 25.0% | Whiff%: 42.9%

  Jesus Luzardo (SP, PHI) (L, 3-1) -- Tampa Bay Rays 7, Philadelphia Phillies 0
    5.0 IP, 7 H, 2 ER, 2 BB, 6 K, 1 HR (88 pitches, 55 strikes)
    Statcast: Whiff%: 22.5% | CSW%: 27.3% | Chase%: 29.5%
             EV Against: 88.0 mph | HardHit%: 31.2% | xBA Against: .332
    Mix: SI: 37.5%, ST: 34.1%, FF: 14.8%, CH: 13.6%
```

## What's in the Brief

| Section | Data |
|---------|------|
| **Hitter highlights** | Box score line (H/AB, HR, RBI, etc.) + Statcast (EV, xBA, barrel%, hard hit%, chase%, whiff%) |
| **Pitcher highlights** | IP/H/ER/BB/K + pitch count + Statcast (whiff%, CSW%, chase rate, EV against, pitch mix) |
| **Minor league** | Box scores for prospects in MiLB games (when season is active) |
| **News & updates** | Fantrax player news from the last 24 hours, sorted by time |
| **Injury watch** | Active IL and injury statuses for your roster |
| **Transactions** | MLB transactions involving your rostered players |
| **Matchup preview** | Today's games with your players + probable pitchers |

## Quick Start

```bash
git clone https://github.com/jack-alex-d/FantasyBrief.git
cd FantasyBrief
python3 setup.py
```

The setup script handles everything:
1. Creates a Python virtual environment
2. Installs all dependencies
3. Asks for your Fantrax league ID and team name
4. Opens a browser for you to log in to Fantrax
5. Runs your first brief

## Daily Usage

```bash
source venv/bin/activate
python daily_brief.py           # Brief for yesterday
python daily_brief.py 2026-04-15  # Brief for a specific date
```

Briefs are saved to `output/brief_YYYY-MM-DD.txt` and also printed to the console.

## Requirements

- Python 3.10+
- A Fantrax fantasy baseball league (private or public)

All data sources are free:
- **Fantrax API** -- roster, scoring, player news (via browser cookie auth)
- **MLB Stats API** -- box scores, transactions, probable pitchers, lineups
- **Baseball Savant / Statcast** -- pitch-level data via pybaseball
- **RotoWire RSS** -- player news headlines

## How It Works

1. Authenticates to Fantrax using saved browser cookies
2. Pulls your team's roster
3. Scans all MLB box scores from the target date, matching your players by name + team
4. Fetches Statcast pitch-level data for each player who appeared in a box score
5. Computes advanced metrics (xBA, barrel%, whiff%, CSW%, chase rate, pitch mix, etc.)
6. Pulls news, transactions, and today's probable pitchers
7. Assembles everything into a readable text brief

## Session Expiry

Fantrax cookies expire periodically. If you see "session expired" errors, just re-login:

```bash
python auth_login.py
```

## Project Structure

```
FantasyBrief/
  setup.py              # One-time setup script
  auth_login.py         # Browser login to save Fantrax cookies
  daily_brief.py        # Main script -- generates the daily brief
  lib/
    fantrax_client.py   # Fantrax API wrapper
    mlb_data.py         # MLB Stats API + Statcast
    news.py             # RSS news feeds
    brief_builder.py    # Text brief formatting
  output/               # Generated briefs
  .env                  # Your league config (not committed)
  cookies.json          # Fantrax session (not committed)
```

## License

MIT
