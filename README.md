# Hyrox Race Day

A 15-week training plan and session tracker for **Hyrox London — Men's Open, Single,
Saturday 5 December 2026**. Target: sub-1:30.

Four tabs: **Today** (tickable session with technique detail), **Plan** (all 15 weeks,
editable), **Reference** (target splits, rules, fuelling, race-day execution) and
**Log** (test results, bodyweight, pace calculator).

## Where each session happens

Every non-rest session carries a location badge, and the exercises in it only use
kit that exists at that location.

| Day | Where | What |
|---|---|---|
| Mon | — | Rest |
| Tue | Home / outdoors | Threshold or easy run, kettlebell and core finisher |
| Wed | Hyrox gym (midday, quiet) | Sled + station work |
| Thu | — | Rest |
| Fri | Hyrox gym (midday, quiet) | Key compromised session; every race simulation |
| Sat | Home / outdoors | Long run |
| Sun | David Lloyd | Easy run + barbell strength (rack) + erg |

The Hyrox gym is the only place with a sled, sandbag, farmers handles and burpee
space, so all sled work and all race simulations live on Wednesday and Friday.
David Lloyd is the only place with a rack, so barbell squats and heavy hinging
live on Sunday. The barbell at home is for deadlifts and shoulders only.

This is a single self-contained page. No accounts, no server, no build step —
open it and it works, including on a plane or in a venue with no signal.

## Where your progress is stored

In the browser you are using, and nowhere else.

Every tick, note, test result and weigh-in is written to that browser's local
storage the moment you make it — there is nothing to remember to save. The
**Save** button is a leftover from the original hosted version; pressing it is
harmless and simply confirms the data is on the device.

The trade-off: **progress does not follow you between devices.** Your phone and
your laptop keep separate copies. If you want to move progress across, open
`backup.html` (the "Backup & restore" page):

1. On the device that has the progress, press **Download backup** or **Copy to clipboard**.
2. On the other device, open the same page, paste it in (or choose the file) and press **Restore**.

Two things that will wipe the progress on a device, so back up before either:
clearing your browser data for the site, or using private/incognito windows.

## Putting it online

The whole point of this copy is a link that works anywhere. GitHub Pages hosts it free.

1. Go to <https://github.com/new>.
2. **Repository name:** `hyrox-race-day`. Leave everything else alone and click
   **Create repository**.
   - Choose **Public** unless you pay for GitHub Pro — Pages does not publish
     private repositories on the free plan. Nothing here is sensitive, but the
     plan and your repo name will be visible to anyone who finds them. Your
     *progress* is never uploaded; it stays in your browser.
3. Push this folder up (the commands are on the page GitHub shows you, and are
   also in the section below).
4. In the repository, click **Settings** → **Pages** in the left sidebar.
5. Under **Build and deployment**, set **Source** to *Deploy from a branch*,
   **Branch** to `main` and the folder to `/ (root)`. Click **Save**.
6. Wait a minute or two, then reload that page — it will show your live URL:
   `https://<your-username>.github.io/hyrox-race-day/`

### Pushing from this folder

```bash
git remote add origin https://github.com/<your-username>/hyrox-race-day.git
```

```bash
git push -u origin main
```

## Putting it on your phone's home screen

Once the site is live it installs like an app — full screen, own icon, works offline.

- **iPhone (Safari):** open the URL → Share button → **Add to Home Screen**.
- **Android (Chrome):** open the URL → ⋮ menu → **Install app** / **Add to Home screen**.

Do this on the phone you will actually train with, and keep the ticking to that
one device. Then a backup is only needed if you change phones.

## Editing the plan

The **Plan** tab has an edit mode — you can retitle any day, and add, reword,
reorder or delete individual items. Edits are stored alongside your progress in
the same browser, so they travel with a backup but do not change the files here.

To change the plan itself for every device, edit the `PLAN` array inside
`index.html`, then bump `CACHE` in `sw.js` (e.g. `hyrox-v1` → `hyrox-v2`) so
installed copies pick the change up instead of serving the cached old one.

## Files

| File | What it is |
|---|---|
| `index.html` | The whole app — plan data, logic and styling in one file |
| `backup.html` | Export and restore your progress as JSON |
| `sw.js` | Service worker; caches the app so it opens offline |
| `manifest.webmanifest` | Makes it installable to a home screen |
| `icons/` | App icons |
| `.nojekyll` | Tells GitHub Pages to serve the files as-is |

## Origin

Extracted from a Claude artifact ("Hyrox Race Day") so it could live somewhere
reachable without being logged in to the account that made it. The app code is
unchanged apart from one message that referred to cloud saving, which does not
apply here.
