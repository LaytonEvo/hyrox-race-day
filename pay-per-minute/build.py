#!/usr/bin/env python3
"""Join reported wages (wages.csv) with live minutes from the Fantasy Premier League API.

Usage: python3 build.py [path/to/bootstrap-static.json]
Without an argument it downloads the FPL data. Writes data.json beside this file.
"""
import csv, re, json, sys, urllib.request, datetime, pathlib, statistics

HERE = pathlib.Path(__file__).resolve().parent
FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
LEFT_LEAGUE = re.compile(r"\bhas joined\b", re.I)  # FPL news for permanent moves and loans out


def left_league(e):
    """FPL keeps departed players in its list, marked unavailable with 'Has joined X ...' news."""
    return e["status"] == "u" and bool(LEFT_LEAGUE.search(e["news"]))


RATING_MIN_MINUTES = 270  # three full matches before a player counts towards the rating scale


def rating_scale(elements):
    """Mean and spread of BPS per 90 for each position, across every PL player with enough minutes."""
    scale = {}
    for pos in POSITIONS:
        vals = [e["bps"] / e["minutes"] * 90 for e in elements
                if e["element_type"] == pos and e["minutes"] >= RATING_MIN_MINUTES]
        if len(vals) >= 5:
            scale[pos] = (statistics.mean(vals), statistics.pstdev(vals) or 1)
    return scale


def rating(e, scale):
    """Turn BPS per 90 into a familiar 4-10 match rating: 6.5 is an average player in that position."""
    if not e["minutes"] or e["element_type"] not in scale:
        return None
    mean, sd = scale[e["element_type"]]
    z = (e["bps"] / e["minutes"] * 90 - mean) / sd
    return round(min(10.0, max(4.0, 6.5 + 0.9 * z)), 2)


def load_fpl(path=None):
    if path:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    req = urllib.request.Request(FPL_URL, headers={"User-Agent": "pay-per-minute/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    fpl = load_fpl(argv[0] if argv else None)
    teams = {t["id"]: t for t in fpl["teams"]}
    by_key = {}
    for e in fpl["elements"]:
        by_key.setdefault((teams[e["team"]]["short_name"], e["web_name"]), []).append(e)

    events = fpl["events"]
    finished = [ev for ev in events if ev["finished"]]
    season_start = events[0]["deadline_time"]
    season = f"{season_start[:4]}/{int(season_start[2:4]) + 1:02d}"

    scale = rating_scale(fpl["elements"])
    players, missing, departed = [], [], []
    with open(HERE / "wages.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            matches = by_key.get((row["team"], row["player"]))
            if not matches or len(matches) > 1:
                missing.append(f'{row["team"]} {row["player"]}' + (" (ambiguous)" if matches else ""))
                continue
            e = matches[0]
            if left_league(e):
                departed.append(f'{row["team"]} {row["player"]}: {e["news"]}')
                continue
            players.append({
                "id": e["id"],
                "name": e["web_name"],
                "full_name": f'{e["first_name"]} {e["second_name"]}',
                "team": row["team"],
                "pos": POSITIONS.get(e["element_type"], "?"),
                "weekly": int(row["weekly_gbp"]),
                "source": row["source"],
                "minutes": e["minutes"],
                "starts": e["starts"],
                "goals": e["goals_scored"],
                "assists": e["assists"],
                "bps": e["bps"],
                "points": e["total_points"],
                "rating": rating(e, scale),
                "xgi": round(float(e["expected_goal_involvements"] or 0), 2),
                "tackles": e["tackles"],
                "recoveries": e["recoveries"],
                "cbi": e["clearances_blocks_interceptions"],
                "defcon": e["defensive_contribution"],
                "og": e["own_goals"],
                "photo": e["photo"].replace(".jpg", ""),
                "status": e["status"],
                "news": e["news"],
            })

    clubs = []
    for t in fpl["teams"]:
        squad = [e for e in fpl["elements"] if e["team"] == t["id"]]
        clubs.append({
            "short": t["short_name"],
            "name": t["name"],
            "played": t["played"] or None,
            "squad_minutes": sum(e["minutes"] for e in squad),
        })

    out = {
        "season": season,
        "season_start": season_start,
        "gameweek": finished[-1]["id"] if finished else 0,
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "rating_min_minutes": RATING_MIN_MINUTES,
        "players": sorted(players, key=lambda p: -p["weekly"]),
        "clubs": clubs,
        "unmatched_wages": missing,
        "left_league": departed,
    }
    tmp = HERE / "data.json.tmp"  # write then rename, so the server never serves a half-written file
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(HERE / "data.json")
    print(f"{len(players)} players written, GW{out['gameweek']}, {len(missing)} unmatched: {missing}, {len(departed)} left the league")


if __name__ == "__main__":
    main()
