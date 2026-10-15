#!/usr/bin/env python3
"""Fetch padel stats from Google Sheets and generate a static website."""

import os

from padel.render import render_html
from padel.stats import parse_matches


def fetch_data():
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ["GOOGLE_SHEETS_API_KEY"]
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/Sheet1?key={api_key}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()["values"]


def main():
    print("Fetching data from Google Sheets...")
    rows = fetch_data()
    matches = parse_matches(rows)
    print(f"Parsed {len(matches)} matches")

    os.makedirs("dist", exist_ok=True)
    html = render_html(matches)
    with open("dist/index.html", "w") as f:
        f.write(html)
    print("Generated dist/index.html")


if __name__ == "__main__":
    main()
