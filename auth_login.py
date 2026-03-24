"""
One-time Fantrax login script.
Opens a browser window for you to log in, then saves session cookies.
Run this once, then use daily_brief.py for daily reports.
"""
import json
import time
from playwright.sync_api import sync_playwright


COOKIES_FILE = "cookies.json"


def main():
    league_id = None
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        league_id = os.getenv("FANTRAX_LEAGUE_ID")
    except ImportError:
        pass

    print("=" * 50)
    print("  Fantrax Login")
    print("=" * 50)
    print()
    print("A browser will open to Fantrax.")
    print("Click 'Login', sign in with your account,")
    print("then come back here and press ENTER.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Go to the main Fantrax page
        start_url = "https://www.fantrax.com/"
        if league_id:
            # Going directly to the league will prompt login if needed
            start_url = f"https://www.fantrax.com/fantasy/league/{league_id}/home"

        page.goto(start_url, wait_until="domcontentloaded")
        print("Browser opened. Please log in to Fantrax now...")
        print()

        # Wait for user to press Enter after logging in
        input(">>> Press ENTER here after you've logged in <<<\n")

        # Save cookies
        cookies = context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)

        print(f"Saved {len(cookies)} cookies to {COOKIES_FILE}")

        # Quick verification -- try loading the league page
        if league_id:
            league_url = f"https://www.fantrax.com/fantasy/league/{league_id}/home"
            try:
                page.goto(league_url, wait_until="domcontentloaded", timeout=10000)
                time.sleep(3)
                body = page.inner_text("body")[:300]
                if "login" in body.lower() and "not found" not in body.lower():
                    print("Note: May still be on login page. Try logging in again and re-running.")
                elif "not found" in body.lower() or "404" in body:
                    print("Note: League page returned 404. Check your league ID.")
                else:
                    print("Login verified -- league page loaded successfully!")
            except Exception:
                print("Could not verify login, but cookies were saved.")

        print("\nYou can now run: python daily_brief.py")
        browser.close()


if __name__ == "__main__":
    main()
