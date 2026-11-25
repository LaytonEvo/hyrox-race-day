# Pay Per Minute

How much every Premier League footballer is paid per minute they actually play.

- `index.html` – the site (static, no build step). Open via any static server or GitHub Pages at `/pay-per-minute/`.
- `wages.csv` – weekly gross wages, one row per player. `team` is the FPL short club code (ARS, MCI…) and `player` is the FPL `web_name` exactly as FPL spells it. **These are reported estimates – correct or extend them freely.**
- `build.py` – pulls live minutes, goals, assists and BPS from the Fantasy Premier League API, joins them to `wages.csv` and writes `data.json`. Any wage row it can't match is listed in `unmatched_wages`.
- `.github/workflows/pay-per-minute.yml` – reruns `build.py` daily and whenever `wages.csv` changes.

## The maths

- Paid so far = weekly wage ÷ 7 × days since the season's first FPL deadline
- £ per minute = paid so far ÷ league minutes
- Idle pay = paid so far × share of available league minutes (gameweeks × 90) the player didn't play
- Rating = BPS per 90 compared with every PL player in the same position with 270+ minutes, on a 4–10 scale (6.5 = average)
- Value score (0–100) = average of the rating percentile and the cheapness percentile (inverse of £ per minute) among tracked players with 270+ minutes
- Price per action = paid so far ÷ goals+assists, xGI, tackles, recoveries or FPL defensive contributions (270+ minutes, at least one action)
- Clubs are ranked only once at least 4 of their players have a wage in `wages.csv`.

## Ideas for next

Full squads for all 20 clubs; cup and European minutes; £ per goal leaderboard; season-by-season history; other leagues.
