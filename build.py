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

        def is_set_won(winner_score, loser_score):
            return winner_score == 7 or (winner_score == 6 and loser_score <= 4)

        sets_won_a = sum(1 for sa, sb in sets if is_set_won(sa, sb))
        sets_won_b = sum(1 for sa, sb in sets if is_set_won(sb, sa))
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
        "current_win_streak": 0, "best_streak": 0, "current_lose_streak": 0,
        "eggs_given": 0, "eggs_received": 0,
    })

    for m in matches:
        for player in m["team_a"]:
            s = stats[player]
            s["matches_played"] += 1
            won = m["winner"] == "A"
            if won:
                s["matches_won"] += 1
                s["current_win_streak"] += 1
                s["current_lose_streak"] = 0
                s["best_streak"] = max(s["best_streak"], s["current_win_streak"])
            elif m["winner"] == "B":
                s["matches_lost"] += 1
                s["current_lose_streak"] += 1
                s["current_win_streak"] = 0
            s["sets_won"] += m["sets_won"][0]
            s["sets_lost"] += m["sets_won"][1]
            s["games_won"] += m["games"][0]
            s["games_lost"] += m["games"][1]
            for sa, sb in m["sets"]:
                if sa == 6 and sb == 0:
                    s["eggs_given"] += 1
                elif sa == 0 and sb == 6:
                    s["eggs_received"] += 1

        for player in m["team_b"]:
            s = stats[player]
            s["matches_played"] += 1
            won = m["winner"] == "B"
            if won:
                s["matches_won"] += 1
                s["current_win_streak"] += 1
                s["current_lose_streak"] = 0
                s["best_streak"] = max(s["best_streak"], s["current_win_streak"])
            elif m["winner"] == "A":
                s["matches_lost"] += 1
                s["current_lose_streak"] += 1
                s["current_win_streak"] = 0
            s["sets_won"] += m["sets_won"][1]
            s["sets_lost"] += m["sets_won"][0]
            s["games_won"] += m["games"][1]
            s["games_lost"] += m["games"][0]
            for sa, sb in m["sets"]:
                if sb == 6 and sa == 0:
                    s["eggs_given"] += 1
                elif sb == 0 and sa == 6:
                    s["eggs_received"] += 1

    # Compute win rate and sort
    leaderboard = []
    for player, s in sorted(stats.items()):
        win_pct = (s["matches_won"] / s["matches_played"] * 100) if s["matches_played"] else 0
        leaderboard.append({"name": player, **s, "win_pct": win_pct})
    leaderboard.sort(key=lambda x: (-x["win_pct"], -x["matches_won"]))
    return leaderboard


def compute_elo(matches, k=32, initial=1500):
    """Compute individual Elo ratings from doubles matches.

    Team strength = average of two players' ratings.
    Both players on each side are updated equally.
    """
    ratings = defaultdict(lambda: initial)

    for m in matches:
        if m["winner"] == "draw":
            continue
        team_a_rating = (ratings[m["team_a"][0]] + ratings[m["team_a"][1]]) / 2
        team_b_rating = (ratings[m["team_b"][0]] + ratings[m["team_b"][1]]) / 2

        expected_a = 1 / (1 + 10 ** ((team_b_rating - team_a_rating) / 400))
        actual_a = 1.0 if m["winner"] == "A" else 0.0

        delta = k * (actual_a - expected_a)
        for player in m["team_a"]:
            ratings[player] += delta
        for player in m["team_b"]:
            ratings[player] -= delta

    # Compute strength of schedule: average opponent and partner Elo
    opp_elos = defaultdict(list)
    partner_elos = defaultdict(list)
    for m in matches:
        if m["winner"] == "draw":
            continue
        for player in m["team_a"]:
            partner = [p for p in m["team_a"] if p != player][0]
            opp_elos[player].append((ratings[m["team_b"][0]] + ratings[m["team_b"][1]]) / 2)
            partner_elos[player].append(ratings[partner])
        for player in m["team_b"]:
            partner = [p for p in m["team_b"] if p != player][0]
            opp_elos[player].append((ratings[m["team_a"][0]] + ratings[m["team_a"][1]]) / 2)
            partner_elos[player].append(ratings[partner])

    result = []
    for p, r in ratings.items():
        avg_opp = round(sum(opp_elos[p]) / len(opp_elos[p])) if opp_elos[p] else initial
        avg_partner = round(sum(partner_elos[p]) / len(partner_elos[p])) if partner_elos[p] else initial
        result.append({"name": p, "elo": round(r), "avg_opp": avg_opp, "avg_partner": avg_partner})
    result.sort(key=lambda x: -x["elo"])
    return result


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
  th[title] { cursor: help; text-decoration: underline dotted; text-underline-offset: 3px; }
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
  .player-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
  }
  .player-btn {
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 0.5rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.15s;
  }
  .player-btn:hover { border-color: var(--accent); }
  .player-btn.selected { background: rgba(56, 189, 248, 0.15); border-color: var(--accent); color: var(--accent); }
  .matchup-result {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem;
    margin-top: 1rem;
  }
  .matchup-vs {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.5rem;
    font-size: 1.1rem;
    margin-bottom: 0.75rem;
  }
  .matchup-team { font-weight: 600; }
  .matchup-vs-label { color: var(--muted); font-size: 0.9rem; }
  .matchup-detail { color: var(--muted); font-size: 0.85rem; text-align: center; }
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
      <th>Partier</th>
      <th title="Antal 6-0 sæt givet / modtaget">Æg</th>
      <th>Streak</th>
      <th>Bedste</th>
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
      <td><span class="win">{{ p.eggs_given }}</span> / <span class="loss">{{ p.eggs_received }}</span></td>
      <td>{% if p.current_win_streak > 0 %}<span class="win">{{ p.current_win_streak }}V</span>{% elif p.current_lose_streak > 0 %}<span class="loss">{{ p.current_lose_streak }}T</span>{% else %}-{% endif %}</td>
      <td>{{ p.best_streak }}V</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Elo Rating</h2>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Spiller</th>
      <th title="Individuel styrke estimeret fra holdresultater. Starter på 1500. Højere = stærkere.">Elo</th>
      <th title="Gennemsnitlig Elo for modstanderholdet. Højere = sværere modstandere.">Gns. Modst.</th>
      <th title="Gennemsnitlig Elo for makkeren. Lavere = mere selvstændigt optjent rating.">Gns. Makker</th>
    </tr>
  </thead>
  <tbody>
    {% for p in elo %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><strong>{{ p.name }}</strong></td>
      <td class="pct">{{ p.elo }}</td>
      <td class="muted">{{ p.avg_opp }}</td>
      <td class="muted">{{ p.avg_partner }}</td>
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

<h2>Anbefalet Holdopstilling</h2>
<p class="subtitle">Vælg dagens 4 spillere og få forslag til makkerpar</p>
<div class="player-grid" id="player-grid"></div>
<div id="matchup-result"></div>

<script>
const elo = {{ elo_json }};
const pairCounts = {{ pair_counts_json }};
const grid = document.getElementById('player-grid');
const result = document.getElementById('matchup-result');
const selected = new Set();

function pairKey(a, b) {
  return [a, b].sort().join(' & ');
}

Object.keys(elo).sort().forEach(name => {
  const btn = document.createElement('button');
  btn.className = 'player-btn';
  btn.textContent = name;
  btn.addEventListener('click', () => {
    if (selected.has(name)) {
      selected.delete(name);
      btn.classList.remove('selected');
    } else if (selected.size < 4) {
      selected.add(name);
      btn.classList.add('selected');
    }
    if (selected.size === 4) recommend();
    else result.innerHTML = '';
  });
  grid.appendChild(btn);
});

function recommend() {
  const players = [...selected];
  const pairings = [
    [[players[0], players[1]], [players[2], players[3]]],
    [[players[0], players[2]], [players[1], players[3]]],
    [[players[0], players[3]], [players[1], players[2]]],
  ];

  // Score each pairing: lower is better
  // Novelty: prefer pairs that have played together fewer times
  // Balance: prefer close Elo matchups
  const scored = pairings.map(([teamA, teamB]) => {
    const eloA = (elo[teamA[0]] + elo[teamA[1]]) / 2;
    const eloB = (elo[teamB[0]] + elo[teamB[1]]) / 2;
    const eloDiff = Math.abs(eloA - eloB);

    const pairsPlayed = (pairCounts[pairKey(teamA[0], teamA[1])] || 0)
                      + (pairCounts[pairKey(teamB[0], teamB[1])] || 0);

    // Combine: novelty (games played * 20) + elo difference
    const score = pairsPlayed * 20 + eloDiff;
    const newPairs = [
      (pairCounts[pairKey(teamA[0], teamA[1])] || 0) === 0 ? pairKey(teamA[0], teamA[1]) : null,
      (pairCounts[pairKey(teamB[0], teamB[1])] || 0) === 0 ? pairKey(teamB[0], teamB[1]) : null,
    ].filter(Boolean);

    return { teamA, teamB, eloA, eloB, eloDiff, pairsPlayed, newPairs, score };
  });

  scored.sort((a, b) => a.score - b.score);
  const best = scored[0];

  const winProb = (1 / (1 + Math.pow(10, (best.eloB - best.eloA) / 400)) * 100).toFixed(0);
  const noveltyNote = best.newPairs.length > 0
    ? `Nyt makkerpar: ${best.newPairs.join(', ')}`
    : '';

  result.innerHTML = `
    <div class="matchup-result">
      <div class="matchup-vs">
        <span class="matchup-team">${best.teamA.join(' & ')}</span>
        <span class="matchup-vs-label">vs</span>
        <span class="matchup-team">${best.teamB.join(' & ')}</span>
      </div>
      <div class="matchup-detail">
        Elo: ${Math.round(best.eloA)} vs ${Math.round(best.eloB)}
        &middot; ${best.teamA.join(' & ')}: ${winProb}%
        ${noveltyNote ? '<br>' + noveltyNote : ''}
      </div>
    </div>
  `;
}
</script>

</body>
</html>
""")


def main():
    print("Fetching data from Google Sheets...")
    rows = fetch_data()
    matches = parse_matches(rows)
    print(f"Parsed {len(matches)} matches")

    leaderboard = compute_player_stats(matches)
    elo = compute_elo(matches)
    pairs = compute_pair_stats(matches)

    os.makedirs("dist", exist_ok=True)
    elo_dict = {p["name"]: p["elo"] for p in elo}
    # Build pair history: how many times each pair has played together
    pair_counts = {}
    for p in pairs:
        pair_counts[p["players"]] = p["played"]
    html = TEMPLATE.render(matches=matches, leaderboard=leaderboard, elo=elo,
                           elo_json=json.dumps(elo_dict),
                           pair_counts_json=json.dumps(pair_counts),
                           pairs=pairs)
    with open("dist/index.html", "w") as f:
        f.write(html)
    print("Generated dist/index.html")


if __name__ == "__main__":
    main()
