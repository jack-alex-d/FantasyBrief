#!/usr/bin/env python3
"""
FantasyBrief Setup Script

Gets you from zero to daily briefs in under 2 minutes.
Handles: Python venv, dependencies, Fantrax config, and browser login.
"""
import json
import os
import subprocess
import sys


COOKIES_FILE = "cookies.json"
ENV_FILE = ".env"


def main():
    print("=" * 55)
    print("  FantasyBrief Setup")
    print("  Daily fantasy baseball briefs with Statcast data")
    print("=" * 55)
    print()

    # Step 1: Python version check
    print("[1/5] Checking Python version...")
    if sys.version_info < (3, 10):
        print(f"  ERROR: Python 3.10+ required (you have {sys.version})")
        sys.exit(1)
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor} -- OK")

    # Step 2: Create venv and install dependencies
    print("\n[2/5] Setting up virtual environment...")
    if not os.path.exists("venv"):
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("  Created venv/")
    else:
        print("  venv/ already exists")

    pip = os.path.join("venv", "bin", "pip") if os.name != "nt" else os.path.join("venv", "Scripts", "pip")
    python = os.path.join("venv", "bin", "python") if os.name != "nt" else os.path.join("venv", "Scripts", "python")

    print("  Installing dependencies (this may take a minute)...")
    result = subprocess.run(
        [pip, "install", "-r", "requirements.txt", "-q"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: pip install failed:\n{result.stderr}")
        sys.exit(1)
    print("  Dependencies installed")

    # Step 2b: Install Playwright browser
    print("  Installing browser for Fantrax login...")
    playwright_bin = os.path.join("venv", "bin", "playwright") if os.name != "nt" else os.path.join("venv", "Scripts", "playwright")
    result = subprocess.run(
        [playwright_bin, "install", "chromium"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        # Try via python -m
        subprocess.run([python, "-m", "playwright", "install", "chromium"], capture_output=True)
    print("  Browser ready")

    # Step 3: Configure league
    print("\n[3/5] Configuring your Fantrax league...")
    if os.path.exists(ENV_FILE):
        from dotenv import load_dotenv
        load_dotenv()
        existing_league = os.getenv("FANTRAX_LEAGUE_ID", "")
        existing_team = os.getenv("FANTRAX_TEAM_NAME", "")
        print(f"  Existing config found:")
        print(f"    League ID: {existing_league}")
        print(f"    Team name: {existing_team}")
        reconfigure = input("  Keep this config? [Y/n] ").strip().lower()
        if reconfigure not in ("n", "no"):
            league_id = existing_league
            team_name = existing_team
        else:
            league_id, team_name = _prompt_league_config()
    else:
        league_id, team_name = _prompt_league_config()

    with open(ENV_FILE, "w") as f:
        f.write(f"FANTRAX_LEAGUE_ID={league_id}\n")
        f.write(f"FANTRAX_TEAM_NAME={team_name}\n")
    print(f"  Saved to {ENV_FILE}")

    # Step 4: Fantrax login
    print("\n[4/5] Fantrax login...")
    if os.path.exists(COOKIES_FILE):
        relogin = input("  cookies.json exists. Re-login? [y/N] ").strip().lower()
        if relogin not in ("y", "yes"):
            print("  Keeping existing session")
        else:
            _do_fantrax_login(python, league_id)
    else:
        _do_fantrax_login(python, league_id)

    # Step 5: Test run
    print("\n[5/5] Running a test brief...")
    result = subprocess.run(
        [python, "daily_brief.py"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode == 0:
        # Find the output file
        for line in result.stdout.splitlines():
            if "Brief written to:" in line:
                print(f"  {line.strip()}")
                break
        print("\n  Setup complete! Your first brief has been generated.")
    else:
        print("  Brief generation had issues (may need Fantrax re-login):")
        # Show last few lines of output
        for line in result.stdout.splitlines()[-5:]:
            print(f"    {line}")
        if result.stderr:
            for line in result.stderr.splitlines()[-3:]:
                print(f"    {line}")

    print()
    print("=" * 55)
    print("  You're all set!")
    print("=" * 55)
    print()
    print("  Daily usage:")
    print("    source venv/bin/activate && python daily_brief.py")
    print()
    print("  For a specific date:")
    print("    python daily_brief.py 2026-03-22")
    print()
    print("  If your session expires:")
    print("    python auth_login.py")
    print()


def _prompt_league_config() -> tuple[str, str]:
    print()
    print("  To find your league ID, go to your Fantrax league page.")
    print("  The URL looks like: fantrax.com/fantasy/league/XXXXX/home")
    print("  The XXXXX part is your league ID.")
    print()
    league_id = input("  Fantrax League ID: ").strip()
    team_name = input("  Your team name (as shown in Fantrax): ").strip()
    return league_id, team_name


def _do_fantrax_login(python: str, league_id: str):
    print("  Opening browser for Fantrax login...")
    print("  Log in to your account, then come back and press ENTER.")
    print()
    # Run auth_login.py interactively (needs terminal input)
    try:
        subprocess.run([python, "auth_login.py"], check=False)
    except KeyboardInterrupt:
        print("\n  Login cancelled.")
        return

    if os.path.exists(COOKIES_FILE):
        # Strip non-Fantrax cookies
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        fantrax_only = [c for c in cookies if "fantrax.com" in c.get("domain", "")]
        with open(COOKIES_FILE, "w") as f:
            json.dump(fantrax_only, f, indent=2)
        print(f"  Saved {len(fantrax_only)} Fantrax cookies")
    else:
        print("  WARNING: No cookies saved. You may need to re-run setup.")


if __name__ == "__main__":
    main()
