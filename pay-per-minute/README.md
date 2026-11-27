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
- Price per action = paid so far ÷ goals, assists, own goals, goals+assists, xGI, tackles, recoveries or FPL defensive contributions (270+ minutes, at least one action)
- Team breakdown = a club's tracked players: paid so far ÷ goals, assists, goals+assists and minutes
- Units: prices can be shown in meal deals, pints, sausage rolls, Freddos, match tickets, replica shirts, season tickets, UK average salaries or houses – edit `UNITS` in index.html
- Actions are position-aware: goals/assists/xGI/tackles/recoveries/defensive actions are outfield-only; saves, penalty saves and goals conceded are keeper-only; clean sheets are GK+DEF; own goals apply to everyone
- Every page has a position filter (All/GK/DEF/MID/FWD) that stays set across pages
- Team of the week (4-3-3, per gameweek): match rating = gameweek BPS vs same-position players with 60+ minutes; Value XI = best value, Overpaid XI = worst, Paid to watch XI = best-paid tracked players with 0 minutes
- Managers: managers.csv (team, manager, annual salary, start/end dates for mid-season changes, source). Points and records come from the FPL fixtures feed, counted only during each manager's spell; £ per point = paid so far ÷ points
- North v South: North = North + Midlands clubs (Severn–Wash line), South = London, south coast, Ipswich; plus region table and 7 derbies
- Games: /game/ (Higher or lower), /guess-the-wage/ (slider guess, 100 pts per player, log-scale scoring), /what-costs-more/ (football cost v real-world price), /daily/ (five-round daily challenge, same for everyone each UK day; picks are ranked by a hash of the date so data refreshes don't change the puzzle; results and streaks stay in the player's browser)
- Crawlable pages: site_pages.py renders /players/, /clubs/, /premier-league-wages/, /team-of-the-week/ (+ /gameweek-N/), /north-south-divide/, /premier-league-manager-salaries/, sitemap.xml
- Clubs are ranked only once at least 4 of their players have a wage in `wages.csv`.

## Ideas for next

Full squads for all 20 clubs; cup and European minutes; £ per goal leaderboard; season-by-season history; other leagues.
