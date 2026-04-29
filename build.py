#!/usr/bin/env python3
"""Fetch padel stats from Google Sheets and generate a static website."""

import json
import os
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader

_template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
_env = Environment(loader=FileSystemLoader(_template_dir))


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


def parse_matches(rows):
    """Parse raw sheet rows into match dicts."""
    matches = []
    for row in rows[2:]:  # skip header rows
        if len(row) < 8:
            continue
        date = row[0]
        sted = row[1].strip()
        team_a = [row[2].strip(), row[3].strip()]
        team_b = [row[4].strip(), row[5].strip()]

        sets = []
        for i in range(6, len(row) - 1, 2):
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
            "sted": sted,
            "team_a": team_a,
            "team_b": team_b,
            "sets": sets,
            "sets_won": (sets_won_a, sets_won_b),
            "games": (games_a, games_b),
            "winner": winner,
        })
    return matches


VENUES = ["begge", "inde", "ude"]


def filter_by_venue(matches, venue):
    """Return matches at the given venue. 'begge' returns all matches."""
    if venue == "begge":
        return list(matches)
    label = venue.capitalize()
    return [m for m in matches if m["sted"] == label]


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


TEMPLATE = _env.get_template("index.html")


def build_venue_data(matches):
    """Compute leaderboard/Elo/pairs for each venue (begge/inde/ude)."""
    venue_data = {}
    for venue in VENUES:
        subset = filter_by_venue(matches, venue)
        leaderboard = compute_player_stats(subset)
        elo, elo_history = compute_elo(subset)
        pairs = compute_pair_stats(subset)
        venue_data[venue] = {
            "leaderboard": leaderboard,
            "elo": elo,
            "pairs": pairs,
            "elo_dict": {p["name"]: p["elo"] for p in elo},
            "pair_counts": {p["players"]: p["played"] for p in pairs},
            "elo_history": dict(elo_history),
        }
    return venue_data


def render_html(matches, default_venue="begge"):
    venue_data = build_venue_data(matches)
    venue_json = {
        v: {
            "elo": d["elo_dict"],
            "pairCounts": d["pair_counts"],
            "eloHistory": d["elo_history"],
        }
        for v, d in venue_data.items()
    }
    return TEMPLATE.render(
        matches=matches,
        venues=VENUES,
        default_venue=default_venue,
        venue_data=venue_data,
        venue_data_json=json.dumps(venue_json),
    )


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
