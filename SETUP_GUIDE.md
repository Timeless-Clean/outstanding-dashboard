# Outstanding Dashboard — Setup Guide

Fully automatic, unattended dashboard of outstanding (unpaid) invoices across all
three Timeless entities (SOR, TCCS, TPM), pulled straight from the Xero API.
No PC or browser needs to stay open. Free (GitHub + Xero standard app).

You already did:
- ✅ Created the Xero **Web app** ("Timeless Outstanding Dashboard")
- ✅ Have the **Client ID** and **Client Secret** saved
- ✅ Redirect URI set to `http://localhost:8080/callback`
- ✅ Created the private repo **Timeless-Clean/outstanding-dashboard**

Follow the steps below in order.

---

## STEP 1 — Put these 4 files into your repo
Upload the whole contents of this `github-package` folder to the repo
`Timeless-Clean/outstanding-dashboard` (keep the `.github/workflows/` folder structure):

- `build_dashboard.py`
- `authorize.py`
- `requirements.txt`
- `.github/workflows/update.yml`

(On github.com: "Add file" → "Upload files" → drag them in. For the workflow file,
create it via "Add file → Create new file" and type the path
`.github/workflows/update.yml`, then paste the contents.)

---

## STEP 2 — Get your refresh token (one time, on your PC)
This grants the app access to your 3 organisations.

1. Install Python from https://python.org if you don't have it.
2. Open a terminal / command prompt in the folder that has `authorize.py`.
3. Run:
   ```
   pip install requests
   ```
4. Set your credentials (Windows Command Prompt):
   ```
   set XERO_CLIENT_ID=your_client_id
   set XERO_CLIENT_SECRET=your_client_secret
   python authorize.py
   ```
   (Mac/Linux: use `export` instead of `set`.)
5. A browser opens → log in to Xero → on the **allow access** screen
   **tick ALL THREE organisations** (TPM, SOR, TCC) → **Allow**.
6. The terminal prints a long **REFRESH TOKEN**. Copy it.

---

## STEP 3 — Add the 3 secrets to GitHub
In the repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add these three (names must match exactly):

| Name | Value |
|------|-------|
| `XERO_CLIENT_ID` | your Client ID |
| `XERO_CLIENT_SECRET` | your Client Secret |
| `XERO_REFRESH_TOKEN` | the refresh token from Step 2 |

---

## STEP 4 — First run
1. Repo → **Actions** tab → if prompted, click **"I understand my workflows, enable them"**.
2. Click **"Update outstanding dashboard"** → **Run workflow** → **Run workflow**.
3. Wait ~1 min. Green tick = success. It creates `docs/index.html`.

---

## STEP 5 — Turn on the web page (GitHub Pages)
1. Repo → **Settings → Pages**.
2. Source: **Deploy from a branch**. Branch: **main**, folder: **/docs**. Save.
3. After a minute your dashboard is live at:
   ```
   https://timeless-clean.github.io/outstanding-dashboard/
   ```
   Bookmark it. Anyone you share the link with can view it (it's a static page;
   no Xero login needed to view). To keep it private to staff, keep the repo
   private and share the link only internally.

---

## That's it — from now on it's automatic
- Updates by itself on **weekdays, ~9am and ~1pm Sydney time** (may drift ~1h during
  daylight-saving; adjust the two `cron` lines in `update.yml` if you want exact).
- To refresh on demand any time: **Actions → Run workflow**.
- The refresh token renews itself each run (saved to `token.json`) so it never expires
  as long as the schedule runs at least every ~50 days.

### Notes
- If a run ever fails with an auth error, just repeat Step 2 and update the
  `XERO_REFRESH_TOKEN` secret with the new value.
- Next phase (later): the "send payment-reminder email with invoice PDFs" popup —
  this repo is the foundation for it.
