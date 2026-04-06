#!/usr/bin/env python3
"""Fetch padel stats from Google Sheets and generate a static website."""

import os
import json
from collections import defaultdict
from dotenv import load_dotenv
import requests
from jinja2 import Template

load_dotenv()

API_KEY = os.environ["GOOGLE_SHEETS_API_KEY"]
SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEETS_URL = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Sheet1?key={API_KEY}"


def fetch_data():
    resp = requests.get(SHEETS_URL)
    resp.raise_for_status()
    return resp.json()["values"]


def parse_matches(rows):
    """Parse raw sheet rows into match dicts."""
    matches = []
    for row in rows[2:]:  # skip header rows
        if len(row) < 7:
            continue
        date = row[0]
        team_a = [row[1].strip(), row[2].strip()]
        team_b = [row[3].strip(), row[4].strip()]

        sets = []
        for i in range(5, len(row) - 1, 2):
            try:
                score_a = int(row[i])
                score_b = int(row[i + 1])
                sets.append((score_a, score_b))
            except (ValueError, IndexError):
                break

        sets_won_a = sum(1 for sa, sb in sets if sa > sb)
        sets_won_b = sum(1 for sa, sb in sets if sb > sa)
        games_a = sum(sa for sa, sb in sets)
        games_b = sum(sb for sa, sb in sets)

        if sets_won_a > sets_won_b:
            winner = "A"
        elif sets_won_b > sets_won_a:
            winner = "B"
        else:
            winner = "draw"

        matches.append({
            "date": date,
            "team_a": team_a,
            "team_b": team_b,
            "sets": sets,
            "sets_won": (sets_won_a, sets_won_b),
            "games": (games_a, games_b),
            "winner": winner,
        })
    return matches


def compute_player_stats(matches):
    """Compute per-player win/loss/sets/games stats."""
    stats = defaultdict(lambda: {
        "matches_played": 0, "matches_won": 0, "matches_lost": 0,
        "sets_won": 0, "sets_lost": 0, "games_won": 0, "games_lost": 0,
    })

    for m in matches:
        for player in m["team_a"]:
            s = stats[player]
            s["matches_played"] += 1
            if m["winner"] == "A":
                s["matches_won"] += 1
            elif m["winner"] == "B":
                s["matches_lost"] += 1
            s["sets_won"] += m["sets_won"][0]
            s["sets_lost"] += m["sets_won"][1]
            s["games_won"] += m["games"][0]
            s["games_lost"] += m["games"][1]

        for player in m["team_b"]:
            s = stats[player]
            s["matches_played"] += 1
            if m["winner"] == "B":
                s["matches_won"] += 1
            elif m["winner"] == "A":
                s["matches_lost"] += 1
            s["sets_won"] += m["sets_won"][1]
            s["sets_lost"] += m["sets_won"][0]
            s["games_won"] += m["games"][1]
            s["games_lost"] += m["games"][0]

    # Compute win rate and sort
    leaderboard = []
    for player, s in sorted(stats.items()):
        win_pct = (s["matches_won"] / s["matches_played"] * 100) if s["matches_played"] else 0
        leaderboard.append({"name": player, **s, "win_pct": win_pct})
    leaderboard.sort(key=lambda x: (-x["win_pct"], -x["matches_won"]))
    return leaderboard


def compute_pair_stats(matches):
    """Compute stats for each player pair (partnership)."""
    pairs = defaultdict(lambda: {"played": 0, "won": 0, "lost": 0})

    for m in matches:
        pair_a = tuple(sorted(m["team_a"]))
        pair_b = tuple(sorted(m["team_b"]))

        pairs[pair_a]["played"] += 1
        pairs[pair_b]["played"] += 1

        if m["winner"] == "A":
            pairs[pair_a]["won"] += 1
            pairs[pair_b]["lost"] += 1
        elif m["winner"] == "B":
            pairs[pair_b]["won"] += 1
            pairs[pair_a]["lost"] += 1

    result = []
    for (p1, p2), s in pairs.items():
        win_pct = (s["won"] / s["played"] * 100) if s["played"] else 0
        result.append({"players": f"{p1} & {p2}", **s, "win_pct": win_pct})
    result.sort(key=lambda x: (-x["win_pct"], -x["won"]))
    return result


TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Padel Stats</title>
<style>
  :root {
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --green: #4ade80;
    --red: #f87171;
    --yellow: #fbbf24;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 2rem 1rem;
    max-width: 960px;
    margin: 0 auto;
  }
  h1 { font-size: 2rem; margin-bottom: 0.25rem; }
  .subtitle { color: var(--muted); margin-bottom: 2rem; }
  h2 {
    font-size: 1.25rem;
    color: var(--accent);
    margin: 2.5rem 0 1rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }
  th, td {
    padding: 0.5rem 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }
  th { color: var(--muted); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
  tr:hover { background: rgba(56, 189, 248, 0.05); }
  .win { color: var(--green); font-weight: 600; }
  .loss { color: var(--red); font-weight: 600; }
  .pct { color: var(--yellow); }
  .set-score { font-variant-numeric: tabular-nums; }
  .winner-marker { color: var(--green); }
  .badge {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
  }
  .badge-win { background: rgba(74, 222, 128, 0.15); color: var(--green); }
  .badge-loss { background: rgba(248, 113, 113, 0.15); color: var(--red); }
  @media (max-width: 640px) {
    body { padding: 1rem 0.5rem; }
    th, td { padding: 0.4rem; font-size: 0.8rem; }
  }
</style>
</head>
<body>

<h1>Padel Stats</h1>
<p class="subtitle">{{ matches|length }} kampe spillet</p>

<h2>Leaderboard</h2>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Spiller</th>
      <th>K</th>
      <th>V</th>
      <th>T</th>
      <th>V%</th>
      <th>Sæt</th>
      <th>Gems</th>
    </tr>
  </thead>
  <tbody>
    {% for p in leaderboard %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><strong>{{ p.name }}</strong></td>
      <td>{{ p.matches_played }}</td>
      <td class="win">{{ p.matches_won }}</td>
      <td class="loss">{{ p.matches_lost }}</td>
      <td class="pct">{{ "%.0f"|format(p.win_pct) }}%</td>
      <td>{{ p.sets_won }}-{{ p.sets_lost }}</td>
      <td>{{ p.games_won }}-{{ p.games_lost }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Makkerpar</h2>
<table>
  <thead>
    <tr>
      <th>Par</th>
      <th>K</th>
      <th>V</th>
      <th>T</th>
      <th>V%</th>
    </tr>
  </thead>
  <tbody>
    {% for p in pairs %}
    <tr>
      <td><strong>{{ p.players }}</strong></td>
      <td>{{ p.played }}</td>
      <td class="win">{{ p.won }}</td>
      <td class="loss">{{ p.lost }}</td>
      <td class="pct">{{ "%.0f"|format(p.win_pct) }}%</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Kamphistorik</h2>
<table>
  <thead>
    <tr>
      <th>Dato</th>
      <th>Hold A</th>
      <th>Hold B</th>
      <th>Sæt</th>
      <th>Resultat</th>
    </tr>
  </thead>
  <tbody>
    {% for m in matches|reverse %}
    <tr>
      <td>{{ m.date }}</td>
      <td{% if m.winner == 'A' %} class="win"{% endif %}>{{ m.team_a|join(' & ') }}</td>
      <td{% if m.winner == 'B' %} class="win"{% endif %}>{{ m.team_b|join(' & ') }}</td>
      <td class="set-score">
        {% for sa, sb in m.sets %}
          {{ sa }}-{{ sb }}{% if not loop.last %}, {% endif %}
        {% endfor %}
      </td>
      <td>
        {% if m.winner == 'A' %}
          <span class="badge badge-win">{{ m.team_a|join(' & ') }}</span>
        {% elif m.winner == 'B' %}
          <span class="badge badge-win">{{ m.team_b|join(' & ') }}</span>
        {% else %}
          <span class="badge">Uafgjort</span>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>

</body>
</html>
""")


def main():
    print("Fetching data from Google Sheets...")
    rows = fetch_data()
    matches = parse_matches(rows)
    print(f"Parsed {len(matches)} matches")

    leaderboard = compute_player_stats(matches)
    pairs = compute_pair_stats(matches)

    os.makedirs("dist", exist_ok=True)
    html = TEMPLATE.render(matches=matches, leaderboard=leaderboard, pairs=pairs)
    with open("dist/index.html", "w") as f:
        f.write(html)
    print("Generated dist/index.html")


if __name__ == "__main__":
    main()
