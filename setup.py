#!/usr/bin/env python3
"""
FantasyBrief Setup Script

Gets you from zero to daily briefs in under 2 minutes.
Handles: Python venv, dependencies, Fantrax config, email, scheduling.
"""
import json
import os
import plistlib
import subprocess
import sys


COOKIES_FILE = "cookies.json"
ENV_FILE = ".env"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PLIST_NAME = "com.fantasybrief.daily"
PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_NAME}.plist")


def main():
    print("=" * 55)
    print("  FantasyBrief Setup")
    print("  Daily fantasy baseball briefs with Statcast data")
    print("=" * 55)
    print()

    # Step 1: Python version check
    print("[1/6] Checking Python version...")
    if sys.version_info < (3, 10):
        print(f"  ERROR: Python 3.10+ required (you have {sys.version})")
        sys.exit(1)
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor} -- OK")

    # Step 2: Create venv and install dependencies
    print("\n[2/6] Setting up virtual environment...")
    if not os.path.exists("venv"):
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("  Created venv/")
    else:
        print("  venv/ already exists")

    pip = os.path.join("venv", "bin", "pip") if os.name != "nt" else os.path.join("venv", "Scripts", "pip")
    python = os.path.join("venv", "bin", "python") if os.name != "nt" else os.path.join("venv", "Scripts", "python")

    # Upgrade pip first
    subprocess.run([pip, "install", "--upgrade", "pip", "-q"], capture_output=True)

    print("  Installing dependencies (this may take a minute)...")
    result = subprocess.run(
        [pip, "install", "-r", "requirements.txt", "-q"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: pip install failed:\n{result.stderr}")
        sys.exit(1)
    print("  Dependencies installed")

    # Install Playwright browser
    print("  Installing browser for Fantrax login...")
    playwright_bin = os.path.join("venv", "bin", "playwright") if os.name != "nt" else os.path.join("venv", "Scripts", "playwright")
    result = subprocess.run(
        [playwright_bin, "install", "chromium"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        subprocess.run([python, "-m", "playwright", "install", "chromium"], capture_output=True)
    print("  Browser ready")

    # Step 3: Configure league
    print("\n[3/6] Configuring your Fantrax league...")
    if os.path.exists(ENV_FILE):
        sys.path.insert(0, os.path.join(PROJECT_DIR, "venv", "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages"))
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        existing_league = os.getenv("FANTRAX_LEAGUE_ID", "")
        existing_team = os.getenv("FANTRAX_TEAM_NAME", "")
        if existing_league:
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
    else:
        league_id, team_name = _prompt_league_config()

    # Step 4: Email setup
    print("\n[4/6] Email delivery (optional)...")
    print("  FantasyBrief can email you the brief each day.")
    print("  Uses Resend (free, 100 emails/day, no personal email password needed).")
    print()
    setup_email = input("  Set up email delivery? [y/N] ").strip().lower()
    email_lines = ""
    if setup_email in ("y", "yes"):
        print()
        print("  1. Go to https://resend.com and create a free account")
        print("  2. Go to https://resend.com/api-keys and create an API key")
        print()
        resend_key = input("  Resend API key: ").strip()
        email_to = input("  Send briefs to (email, comma-separated for multiple): ").strip()
        email_lines = (
            f"RESEND_API_KEY={resend_key}\n"
            f"EMAIL_TO={email_to}\n"
        )
        print("  Email configured!")

    # Write .env
    with open(ENV_FILE, "w") as f:
        f.write(f"FANTRAX_LEAGUE_ID={league_id}\n")
        f.write(f"FANTRAX_TEAM_NAME={team_name}\n")
        if email_lines:
            f.write(email_lines)
    print(f"  Config saved to {ENV_FILE}")

    # Step 5: Fantrax login
    print("\n[5/6] Fantrax login...")
    if os.path.exists(COOKIES_FILE):
        relogin = input("  cookies.json exists. Re-login? [y/N] ").strip().lower()
        if relogin not in ("y", "yes"):
            print("  Keeping existing session")
        else:
            _do_fantrax_login(python, league_id)
    else:
        _do_fantrax_login(python, league_id)

    # Step 6: Schedule daily run
    print("\n[6/6] Daily scheduling (optional)...")
    if sys.platform == "darwin":
        _setup_launchd(python)
    else:
        _setup_cron(python)

    # Test run
    print("\nRunning a test brief...")
    email_flag = ["--email"] if email_lines else []
    result = subprocess.run(
        [python, "daily_brief.py"] + email_flag,
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if "Brief written to:" in line:
                print(f"  {line.strip()}")
                break
            if "Email sent" in line:
                print(f"  {line.strip()}")
        print("\n  Setup complete!")
    else:
        print("  Brief generation had issues:")
        for line in result.stdout.splitlines()[-5:]:
            print(f"    {line}")

    print()
    print("=" * 55)
    print("  You're all set!")
    print("=" * 55)
    print()
    print("  Manual usage:")
    print("    source venv/bin/activate && python daily_brief.py")
    print()
    print("  With email:")
    print("    python daily_brief.py --email")
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
    try:
        subprocess.run([python, "auth_login.py"], check=False)
    except KeyboardInterrupt:
        print("\n  Login cancelled.")
        return

    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        fantrax_only = [c for c in cookies if "fantrax.com" in c.get("domain", "")]
        with open(COOKIES_FILE, "w") as f:
            json.dump(fantrax_only, f, indent=2)
        print(f"  Saved {len(fantrax_only)} Fantrax cookies")
    else:
        print("  WARNING: No cookies saved. You may need to re-run setup.")


def _setup_launchd(python: str):
    """Set up macOS launchd to run the brief daily at 10 AM ET."""
    setup_schedule = input("  Set up daily auto-run at 10 AM? [y/N] ").strip().lower()
    if setup_schedule not in ("y", "yes"):
        print("  Skipping scheduling.")
        return

    python_abs = os.path.join(PROJECT_DIR, python)
    script_abs = os.path.join(PROJECT_DIR, "daily_brief.py")
    log_path = os.path.join(PROJECT_DIR, "output", "launchd.log")

    plist = {
        "Label": PLIST_NAME,
        "ProgramArguments": [python_abs, script_abs, "--email"],
        "WorkingDirectory": PROJECT_DIR,
        "StartCalendarInterval": {"Hour": 10, "Minute": 0},
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
        "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/local/bin"},
    }

    os.makedirs(os.path.dirname(PLIST_PATH), exist_ok=True)

    # Unload existing if present
    if os.path.exists(PLIST_PATH):
        subprocess.run(["launchctl", "unload", PLIST_PATH], capture_output=True)

    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)

    result = subprocess.run(["launchctl", "load", PLIST_PATH], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  Scheduled! Brief will run daily at 10:00 AM.")
        print(f"  If your Mac is asleep at 10 AM, it runs when it wakes.")
        print(f"  Plist: {PLIST_PATH}")
        print(f"  Log: {log_path}")
    else:
        print(f"  Scheduling failed: {result.stderr}")
        print(f"  Plist saved to {PLIST_PATH} -- you can load it manually:")
        print(f"    launchctl load {PLIST_PATH}")


def _setup_cron(python: str):
    """Fallback: offer cron instructions for non-macOS."""
    print("  To schedule daily runs, add this to your crontab (crontab -e):")
    python_abs = os.path.join(PROJECT_DIR, python)
    script_abs = os.path.join(PROJECT_DIR, "daily_brief.py")
    print(f"    0 10 * * * cd {PROJECT_DIR} && {python_abs} {script_abs} --email")


if __name__ == "__main__":
    main()
