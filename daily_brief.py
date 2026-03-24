"""
Daily Fantasy Baseball Brief Generator.

Pulls data from Fantrax, MLB Stats API, Statcast, and news feeds
to generate a comprehensive daily report for your fantasy team.

Usage:
    python daily_brief.py              # Brief for yesterday
    python daily_brief.py 2026-03-22   # Brief for specific date
    python daily_brief.py --email      # Brief for yesterday + send email
    python daily_brief.py 2026-03-22 --email
"""
import os
import smtplib
import ssl
import sys
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText

from dotenv import load_dotenv

from lib.fantrax_client import FantraxClient
from lib.mlb_data import (
    compute_batter_metrics,
    compute_pitcher_metrics,
    get_all_player_box_scores,
    get_milb_player_stats,
    get_statcast_batter_day,
    get_statcast_pitcher_day,
    get_todays_probable_pitchers,
    get_transactions,
    get_yesterdays_games,
)
from lib.news import fetch_rotowire_news, filter_news_for_players
from lib.brief_builder import build_brief


def main():
    load_dotenv()
    league_id = os.getenv("FANTRAX_LEAGUE_ID")
    team_name = os.getenv("FANTRAX_TEAM_NAME", "My Team")

    if not league_id:
        print("Error: Set FANTRAX_LEAGUE_ID in .env")
        sys.exit(1)

    # Parse arguments
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    send_email = "--email" in flags

    if args:
        try:
            target_date = datetime.strptime(args[0], "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date format: {args[0]}. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date = date.today() - timedelta(days=1)

    print(f"Generating brief for {team_name} -- {target_date}")
    print()

    # Step 1: Fantrax data
    roster = []
    scoring_data = {}
    try:
        print("[1/6] Connecting to Fantrax...")
        client = FantraxClient(league_id)
        team_id = client.find_team_id(team_name)
        if team_id:
            print(f"  Found team: {team_name} (ID: {team_id})")
            roster = client.get_roster(team_id)
            print(f"  Roster: {len(roster)} players")
            scoring_data = client.get_matchup_scores()
        else:
            teams = client.get_teams()
            print(f"  Could not find '{team_name}'. Available teams:")
            for tid, tname in teams.items():
                print(f"    - {tname} ({tid})")
    except FileNotFoundError:
        print("  No cookies.json found. Run: python auth_login.py")
        print("  Continuing without Fantrax data...")
    except PermissionError as e:
        print(f"  {e}")
        print("  Continuing without Fantrax data...")
    except Exception as e:
        print(f"  Fantrax error: {e}")
        print("  Continuing without Fantrax data...")

    # Step 2: Check for games
    print(f"\n[2/6] Checking MLB games for {target_date}...")
    games = get_yesterdays_games(target_date)
    print(f"  Found {len(games)} completed games")

    if not games:
        print("  No games played -- generating abbreviated brief.")

    # Step 3: Box scores + Statcast for roster players
    player_names = [p.get("name", "") for p in roster if p.get("name")]
    box_scores = {}
    batter_statcast = {}
    pitcher_statcast = {}
    milb_stats = {}

    if games and player_names:
        # Batch fetch all box score stat lines in one pass
        print(f"\n[3/6] Pulling box scores and Statcast for {len(player_names)} players...")
        print("  Scanning box scores...", end=" ", flush=True)
        box_scores = get_all_player_box_scores(roster, target_date)
        played = [n for n, d in box_scores.items()]
        print(f"{len(box_scores)} players found in box scores")

        # Pull Statcast only for players who actually played
        hitters = [p for p in roster if _is_hitter(p)]
        pitchers = [p for p in roster if _is_pitcher(p)]

        hitters_who_played = [p for p in hitters if p.get("name") in box_scores]
        pitchers_who_played = [p for p in pitchers if p.get("name") in box_scores]

        for i, player in enumerate(hitters_who_played):
            name = player["name"]
            person_id = box_scores.get(name, {}).get("person_id")
            print(f"  Statcast {i+1}/{len(hitters_who_played)}: {name}...", end=" ", flush=True)
            df = get_statcast_batter_day(name, target_date, mlbam_id=person_id)
            if not df.empty:
                metrics = compute_batter_metrics(df)
                if metrics:
                    batter_statcast[name] = metrics
                    print(f"OK ({metrics.get('pitches_seen', 0)} pitches)")
                else:
                    print("no batted balls")
            else:
                print("no Statcast")

        for i, player in enumerate(pitchers_who_played):
            name = player["name"]
            person_id = box_scores.get(name, {}).get("person_id")
            print(f"  Statcast {i+1}/{len(pitchers_who_played)}: {name}...", end=" ", flush=True)
            df = get_statcast_pitcher_day(name, target_date, mlbam_id=person_id)
            if not df.empty:
                metrics = compute_pitcher_metrics(df)
                if metrics:
                    pitcher_statcast[name] = metrics
                    print(f"OK ({metrics.get('total_pitches', 0)} pitches)")
                else:
                    print("no data")
            else:
                print("no Statcast")

        # Check MiLB for players without MLB box score data
        dnp_players = [p for p in hitters + pitchers if p.get("name") and p["name"] not in box_scores]
        if dnp_players:
            print(f"\n  Checking MiLB for {len(dnp_players)} players without MLB data...")
            for player in dnp_players:
                name = player.get("name", "")
                if not name:
                    continue
                result = get_milb_player_stats(name, target_date)
                if result:
                    milb_stats[name] = result
                    print(f"    {name}: Found {result['level']} data ({result['game']})")
    else:
        print("\n[3/6] Skipping stats (no games or no roster)")

    # Step 4: News
    print("\n[4/6] Fetching news...")
    all_news = fetch_rotowire_news(hours_back=24)
    print(f"  Fetched {len(all_news)} news items")
    if player_names:
        relevant_news = filter_news_for_players(all_news, player_names)
        print(f"  {len(relevant_news)} items relevant to your roster")
    else:
        relevant_news = all_news[:10]
        print("  No roster to filter against, showing top 10")

    # Step 5: Transactions
    print("\n[5/6] Fetching transactions...")
    transactions = get_transactions(target_date)
    print(f"  {len(transactions)} transactions found")

    # Step 6: Probable pitchers for today
    print("\n[6/6] Fetching today's probable pitchers...")
    probables = get_todays_probable_pitchers()
    print(f"  {len(probables)} games scheduled")

    # Build the brief
    print("\nBuilding brief...")
    brief_text = build_brief(
        team_name=team_name,
        roster=roster,
        scoring_data=scoring_data,
        box_scores=box_scores,
        batter_statcast=batter_statcast,
        pitcher_statcast=pitcher_statcast,
        milb_stats=milb_stats,
        news_items=relevant_news,
        transactions=transactions,
        probable_pitchers=probables,
        target_date=target_date,
    )

    # Write to file
    os.makedirs("output", exist_ok=True)
    filename = f"output/brief_{target_date.strftime('%Y-%m-%d')}.txt"
    with open(filename, "w") as f:
        f.write(brief_text)

    print(f"\nBrief written to: {filename}")
    print(f"({len(brief_text)} characters, {brief_text.count(chr(10))} lines)")

    # Send email if requested
    if send_email:
        _send_email(brief_text, team_name, target_date)

    print()
    print(brief_text)


def _send_email(brief_text: str, team_name: str, target_date: date):
    """Send the brief via SMTP email."""
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    email_from = os.getenv("EMAIL_FROM", smtp_user)
    email_to = os.getenv("EMAIL_TO", "")

    if not all([smtp_host, smtp_user, smtp_pass, email_to]):
        print("\n  Email not configured. Add to .env:")
        print("    SMTP_HOST=smtp.gmail.com")
        print("    SMTP_PORT=587")
        print("    SMTP_USER=you@gmail.com")
        print("    SMTP_PASS=your-app-password")
        print("    EMAIL_FROM=you@gmail.com")
        print("    EMAIL_TO=you@gmail.com")
        return

    subject = f"Fantasy Brief: {team_name} -- {target_date.strftime('%b %d, %Y')}"
    msg = MIMEText(brief_text, "plain")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to

    try:
        print(f"\nSending email to {email_to}...")
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, email_to.split(","), msg.as_string())
        print("  Email sent!")
    except Exception as e:
        print(f"  Email failed: {e}")


def _is_hitter(player: dict) -> bool:
    if "is_pitcher" in player:
        return not player["is_pitcher"]
    pos = player.get("position", "").upper()
    pitcher_positions = {"SP", "RP", "P", "CL"}
    if not pos:
        return True
    return not any(p in pitcher_positions for p in pos.split(","))


def _is_pitcher(player: dict) -> bool:
    if "is_pitcher" in player:
        return player["is_pitcher"]
    pos = player.get("position", "").upper()
    pitcher_positions = {"SP", "RP", "P", "CL"}
    return any(p in pitcher_positions for p in pos.split(","))


if __name__ == "__main__":
    main()
