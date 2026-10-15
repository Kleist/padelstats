"""Render the stats page (templates/index.html) from match dicts."""

import json
import os

from jinja2 import Environment, FileSystemLoader

from padel.stats import VENUES, build_venue_data

_template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
_env = Environment(loader=FileSystemLoader(_template_dir))
TEMPLATE = _env.get_template("index.html")


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
