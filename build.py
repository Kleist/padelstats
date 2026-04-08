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

        # Parse date for sortable ISO format (handles DD/MM/YYYY and DD-MM-YYYY)
        date_sortable = date
        for sep in ('/', '-', '.'):
            parts = date.split(sep)
            if len(parts) == 3:
                try:
                    date_sortable = f"{int(parts[2]):04d}-{int(parts[1]):02d}-{int(parts[0]):02d}"
                except ValueError:
                    pass
                break

        matches.append({
            "date": date,
            "date_sortable": date_sortable,
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
    Returns (results, elo_history) where elo_history maps player name to list
    of {date, date_sortable, elo, won} entries.
    """
    ratings = defaultdict(lambda: initial)
    elo_history = defaultdict(list)

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
            elo_history[player].append({
                "date": m["date"], "date_sortable": m["date_sortable"],
                "elo": round(ratings[player]), "won": m["winner"] == "A",
            })
        for player in m["team_b"]:
            ratings[player] -= delta
            elo_history[player].append({
                "date": m["date"], "date_sortable": m["date_sortable"],
                "elo": round(ratings[player]), "won": m["winner"] == "B",
            })

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
    return result, elo_history


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
  th.sortable { cursor: pointer; user-select: none; }
  th.sortable:hover { color: var(--text); }
  th.sort-asc::after { content: ' \25B2'; font-size: 0.6em; vertical-align: middle; }
  th.sort-desc::after { content: ' \25BC'; font-size: 0.6em; vertical-align: middle; }
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
  .matchup-result + .matchup-result { margin-top: 0.75rem; opacity: 0.5; }
  .matchup-result.recommended { border-color: var(--accent); }
  .matchup-badge { color: var(--accent); font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; text-align: center; }
  .player-link { color: var(--text); cursor: pointer; text-decoration: none; border-bottom: 1px dashed var(--muted); }
  .player-link:hover { color: var(--accent); border-bottom-color: var(--accent); }
  #elo-chart-container {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem;
    margin-top: 1rem;
    display: none;
    position: relative;
  }
  #elo-chart-container.visible { display: block; }
  #elo-chart-title { font-weight: 600; margin-bottom: 0.75rem; }
  #elo-chart-close {
    position: absolute;
    top: 0.75rem;
    right: 1rem;
    background: none;
    border: none;
    color: var(--muted);
    font-size: 1.2rem;
    cursor: pointer;
  }
  #elo-chart-close:hover { color: var(--text); }
  #elo-chart { width: 100%; }
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
      <th class="sortable" data-col="1">Spiller</th>
      <th class="sortable" data-col="2">K</th>
      <th class="sortable" data-col="3">V</th>
      <th class="sortable" data-col="4">T</th>
      <th class="sortable" data-col="5">V%</th>
      <th class="sortable" data-col="6">Sæt</th>
      <th class="sortable" data-col="7">Partier</th>
      <th class="sortable" data-col="8" title="Antal 6-0 sæt givet / modtaget">Æg</th>
      <th class="sortable" data-col="9">Streak</th>
      <th class="sortable" data-col="10">Bedste</th>
    </tr>
  </thead>
  <tbody>
    {% for p in leaderboard %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><strong><a class="player-link" data-player="{{ p.name }}">{{ p.name }}</a></strong></td>
      <td data-sort="{{ p.matches_played }}">{{ p.matches_played }}</td>
      <td class="win" data-sort="{{ p.matches_won }}">{{ p.matches_won }}</td>
      <td class="loss" data-sort="{{ p.matches_lost }}">{{ p.matches_lost }}</td>
      <td class="pct" data-sort="{{ p.win_pct }}">{{ "%.0f"|format(p.win_pct) }}%</td>
      <td data-sort="{{ p.sets_won - p.sets_lost }}">{{ p.sets_won }}-{{ p.sets_lost }}</td>
      <td data-sort="{{ p.games_won - p.games_lost }}">{{ p.games_won }}-{{ p.games_lost }}</td>
      <td data-sort="{{ p.eggs_given - p.eggs_received }}"><span class="win">{{ p.eggs_given }}</span> / <span class="loss">{{ p.eggs_received }}</span></td>
      <td data-sort="{{ p.current_win_streak - p.current_lose_streak }}">{% if p.current_win_streak > 0 %}<span class="win">{{ p.current_win_streak }}V</span>{% elif p.current_lose_streak > 0 %}<span class="loss">{{ p.current_lose_streak }}T</span>{% else %}-{% endif %}</td>
      <td data-sort="{{ p.best_streak }}">{{ p.best_streak }}V</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Elo Rating</h2>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th class="sortable" data-col="1">Spiller</th>
      <th class="sortable" data-col="2" title="Individuel styrke estimeret fra holdresultater. Starter på 1500. Højere = stærkere.">Elo</th>
      <th class="sortable" data-col="3" title="Gennemsnitlig Elo for modstanderholdet. Højere = sværere modstandere.">Gns. Modst.</th>
      <th class="sortable" data-col="4" title="Gennemsnitlig Elo for makkeren. Lavere = mere selvstændigt optjent rating.">Gns. Makker</th>
    </tr>
  </thead>
  <tbody>
    {% for p in elo %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><strong><a class="player-link" data-player="{{ p.name }}">{{ p.name }}</a></strong></td>
      <td class="pct" data-sort="{{ p.elo }}">{{ p.elo }}</td>
      <td class="muted" data-sort="{{ p.avg_opp }}">{{ p.avg_opp }}</td>
      <td class="muted" data-sort="{{ p.avg_partner }}">{{ p.avg_partner }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<div id="elo-chart-container">
  <button id="elo-chart-close">&times;</button>
  <div id="elo-chart-title"></div>
  <canvas id="elo-chart" height="300"></canvas>
</div>

<h2>Makkerpar</h2>
<table>
  <thead>
    <tr>
      <th class="sortable" data-col="0">Par</th>
      <th class="sortable" data-col="1">K</th>
      <th class="sortable" data-col="2">V</th>
      <th class="sortable" data-col="3">T</th>
      <th class="sortable" data-col="4">V%</th>
    </tr>
  </thead>
  <tbody>
    {% for p in pairs %}
    <tr>
      <td><strong>{{ p.players }}</strong></td>
      <td data-sort="{{ p.played }}">{{ p.played }}</td>
      <td class="win" data-sort="{{ p.won }}">{{ p.won }}</td>
      <td class="loss" data-sort="{{ p.lost }}">{{ p.lost }}</td>
      <td class="pct" data-sort="{{ p.win_pct }}">{{ "%.0f"|format(p.win_pct) }}%</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<h2>Kamphistorik</h2>
<table>
  <thead>
    <tr>
      <th class="sortable" data-col="0">Dato</th>
      <th class="sortable" data-col="1">Hold A</th>
      <th class="sortable" data-col="2">Hold B</th>
      <th>Sæt</th>
      <th>Resultat</th>
    </tr>
  </thead>
  <tbody>
    {% for m in matches|reverse %}
    <tr>
      <td data-sort="{{ m.date_sortable }}">{{ m.date }}</td>
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
<div id="matchup-result" style="min-height: 320px;"></div>

<script>
const elo = {{ elo_json }};
const pairCounts = {{ pair_counts_json }};
const eloHistory = {{ elo_history_json }};
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

  result.innerHTML = scored.map((m, i) => {
    const winProb = (1 / (1 + Math.pow(10, (m.eloB - m.eloA) / 400)) * 100).toFixed(0);
    const noveltyNote = m.newPairs.length > 0
      ? `Nyt makkerpar: ${m.newPairs.join(', ')}`
      : '';
    const recommended = i === 0 ? ' recommended' : '';
    return `
      <div class="matchup-result${recommended}">
        ${i === 0 ? '<div class="matchup-badge">Anbefalet</div>' : ''}
        <div class="matchup-vs">
          <span class="matchup-team">${m.teamA.join(' & ')}</span>
          <span class="matchup-vs-label">vs</span>
          <span class="matchup-team">${m.teamB.join(' & ')}</span>
        </div>
        <div class="matchup-detail">
          Elo: ${Math.round(m.eloA)} vs ${Math.round(m.eloB)}
          &middot; ${m.teamA.join(' & ')}: ${winProb}%
          ${noveltyNote ? '<br>' + noveltyNote : ''}
        </div>
      </div>
    `;
  }).join('');
}

// Table sorting
document.querySelectorAll('table').forEach(table => {
  const headers = table.querySelectorAll('th.sortable');
  if (!headers.length) return;
  headers.forEach(th => {
    th.addEventListener('click', () => {
      const col = parseInt(th.dataset.col);
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      const isAsc = th.classList.contains('sort-asc');

      // Clear sort classes on this table's headers
      table.querySelectorAll('th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));

      // Toggle direction
      const dir = isAsc ? 'desc' : 'asc';
      th.classList.add('sort-' + dir);

      rows.sort((a, b) => {
        const aCell = a.cells[col];
        const bCell = b.cells[col];
        const aVal = aCell.dataset.sort !== undefined ? aCell.dataset.sort : aCell.textContent.trim();
        const bVal = bCell.dataset.sort !== undefined ? bCell.dataset.sort : bCell.textContent.trim();
        const aNum = parseFloat(aVal);
        const bNum = parseFloat(bVal);
        if (!isNaN(aNum) && !isNaN(bNum)) {
          return dir === 'asc' ? aNum - bNum : bNum - aNum;
        }
        return dir === 'asc' ? aVal.localeCompare(bVal, 'da') : bVal.localeCompare(aVal, 'da');
      });

      // Re-append sorted rows and renumber '#' column if present
      const firstTh = table.querySelector('th:first-child');
      const hasRank = firstTh && firstTh.textContent.trim() === '#';
      rows.forEach((row, i) => {
        if (hasRank) row.cells[0].textContent = i + 1;
        tbody.appendChild(row);
      });
    });
  });
});

// Elo chart
(function() {
  const container = document.getElementById('elo-chart-container');
  const canvas = document.getElementById('elo-chart');
  const titleEl = document.getElementById('elo-chart-title');
  const closeBtn = document.getElementById('elo-chart-close');

  closeBtn.addEventListener('click', () => container.classList.remove('visible'));

  function drawChart(playerName) {
    const data = eloHistory[playerName];
    if (!data || data.length === 0) return;

    container.classList.add('visible');
    titleEl.textContent = `Elo-udvikling: ${playerName}`;
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = 300 * dpr;
    canvas.style.height = '300px';
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = 300;

    const pad = { top: 20, right: 20, bottom: 40, left: 50 };
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    const elos = data.map(d => d.elo);
    let minElo = Math.min(...elos, 1500);
    let maxElo = Math.max(...elos, 1500);
    const range = maxElo - minElo || 100;
    minElo -= range * 0.1;
    maxElo += range * 0.1;

    function x(i) { return pad.left + (data.length === 1 ? plotW / 2 : (i / (data.length - 1)) * plotW); }
    function y(v) { return pad.top + plotH - ((v - minElo) / (maxElo - minElo)) * plotH; }

    // Clear
    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 0.5;
    const steps = 5;
    for (let i = 0; i <= steps; i++) {
      const val = minElo + (maxElo - minElo) * (i / steps);
      const yy = y(val);
      ctx.beginPath();
      ctx.moveTo(pad.left, yy);
      ctx.lineTo(W - pad.right, yy);
      ctx.stroke();
      ctx.fillStyle = '#94a3b8';
      ctx.font = '11px -apple-system, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(Math.round(val), pad.left - 8, yy + 4);
    }

    // 1500 baseline
    if (minElo < 1500 && maxElo > 1500) {
      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(pad.left, y(1500));
      ctx.lineTo(W - pad.right, y(1500));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Line
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2;
    ctx.beginPath();
    data.forEach((d, i) => {
      const px = x(i), py = y(d.elo);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();

    // Points (win=green, loss=red)
    data.forEach((d, i) => {
      const px = x(i), py = y(d.elo);
      ctx.beginPath();
      ctx.arc(px, py, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = d.won ? '#4ade80' : '#f87171';
      ctx.fill();
    });

    // X-axis date labels (show ~6 evenly spaced)
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px -apple-system, sans-serif';
    ctx.textAlign = 'center';
    const labelCount = Math.min(data.length, 6);
    for (let i = 0; i < labelCount; i++) {
      const idx = data.length === 1 ? 0 : Math.round(i * (data.length - 1) / (labelCount - 1));
      ctx.fillText(data[idx].date, x(idx), H - pad.bottom + 16);
    }
  }

  document.querySelectorAll('.player-link').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      drawChart(link.dataset.player);
    });
  });
})();
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
    elo, elo_history = compute_elo(matches)
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
                           elo_history_json=json.dumps(dict(elo_history)),
                           pairs=pairs)
    with open("dist/index.html", "w") as f:
        f.write(html)
    print("Generated dist/index.html")


if __name__ == "__main__":
    main()
