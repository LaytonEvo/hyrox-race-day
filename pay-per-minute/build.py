#!/usr/bin/env python3
"""Join reported wages (wages.csv) with live minutes from the Fantasy Premier League API.

Usage: python3 build.py [path/to/bootstrap-static.json]
Without an argument it downloads the FPL data. Writes data.json beside this file.
"""
import csv, json, sys, urllib.request, datetime, pathlib

HERE = pathlib.Path(__file__).resolve().parent
FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def load_fpl(path=None):
    if path:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    req = urllib.request.Request(FPL_URL, headers={"User-Agent": "pay-per-minute/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    fpl = load_fpl(sys.argv[1] if len(sys.argv) > 1 else None)
    teams = {t["id"]: t for t in fpl["teams"]}
    by_key = {}
    for e in fpl["elements"]:
        by_key.setdefault((teams[e["team"]]["short_name"], e["web_name"]), []).append(e)

    events = fpl["events"]
    finished = [ev for ev in events if ev["finished"]]
    season_start = events[0]["deadline_time"]
    season = f"{season_start[:4]}/{int(season_start[2:4]) + 1:02d}"

    players, missing = [], []
    with open(HERE / "wages.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            matches = by_key.get((row["team"], row["player"]))
            if not matches or len(matches) > 1:
                missing.append(f'{row["team"]} {row["player"]}' + (" (ambiguous)" if matches else ""))
                continue
            e = matches[0]
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
        "players": sorted(players, key=lambda p: -p["weekly"]),
        "clubs": clubs,
        "unmatched_wages": missing,
    }
    (HERE / "data.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(players)} players written, GW{out['gameweek']}, {len(missing)} unmatched: {missing}")


if __name__ == "__main__":
    main()
