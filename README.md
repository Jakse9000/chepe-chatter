# Chepe Chatter — your news site

This folder is a complete, working website that builds itself. It reads Costa Rican
news feeds, keeps what matters to foreigners, translates Spanish ↔ English, and
publishes a finished page. Once it's on GitHub, it updates **every hour on its own**
and hosting is **free**.

You don't need to understand the code. Follow the steps below in order. Each step
says exactly what to click. Take your time — nothing here can break anything.

---

## What's in this folder

| File | What it is |
|---|---|
| `feeds.yaml` | **The only file you'll normally edit.** Your list of news sources and events. |
| `build.py` | The program that builds the site. You run it; you don't edit it. |
| `classify.py` | Keyword rules that decide "is this relevant to foreigners?" (the fallback). |
| `classify_ai.py` | Optional smarter sorting using Claude. Turns on when you add an API key. |
| `events.py` | Collects upcoming cultural events automatically from GAM Cultural. |
| `translate.py` | The translator. Free now; ready for DeepL later. |
| `templates/index.html` | The page design (your approved prototype). |
| `.github/workflows/build.yml` | The "robot" that rebuilds the site hourly on GitHub. |
| `requirements.txt` | The list of helper libraries GitHub installs automatically. |

---

## Part A — Put it on GitHub (one time, ~20 minutes)

> **On Pop!_OS / Linux with a terminal?** Use this quick path, then skip to step 4.
> First make a free account at https://github.com, then create a new **empty** repo
> named `chepe-chatter` on the website (no README). Then, from this folder:
> ```bash
> sudo apt install -y git           # if you don't already have it
> cd path/to/chepe-chatter          # this folder
> git init
> git add .
> git commit -m "first version"
> git branch -M main
> git remote add origin https://github.com/YOUR-USERNAME/chepe-chatter.git
> git push -u origin main
> ```
> GitHub will ask you to log in (use a Personal Access Token as the password —
> github.com → Settings → Developer settings → Tokens). Then go to **step 4** below.
> To test locally first: `pip install -r requirements.txt && python3 build.py`,
> then open `site/index.html`.
>
> Prefer clicking to typing? The GitHub Desktop steps below work too.

### 1. Make a free GitHub account
Go to https://github.com and sign up. It's free.

### 2. Install GitHub Desktop (no command line needed)
Download from https://desktop.github.com and install it. Sign in with your new account.
This is a friendly app that moves files to GitHub by clicking buttons.

### 3. Create the repository
- In GitHub Desktop: **File → New Repository**.
- Name: `chepe-chatter`
- Local path: pick where to keep it on your computer.
- Click **Create Repository**.
- Open that new folder on your computer and **copy every file from this folder into it**
  (including the hidden `.github` folder — turn on "show hidden files" if needed).
- Back in GitHub Desktop you'll see all the files listed. Type a summary like
  "first version" and click **Commit to main**, then **Publish repository**.
  Leave "Keep this code private" **unchecked** (Pages needs it public on the free plan).

### 4. Turn on GitHub Pages (the free hosting)
- On github.com, open your `chepe-chatter` repository.
- **Settings → Pages** (left menu).
- Under "Build and deployment", set **Source = GitHub Actions**. That's it.

### 5. Run it for the first time
- Go to the **Actions** tab of your repository.
- If asked, click the green button to enable workflows.
- Click **"Build & deploy Chepe Chatter"** → **Run workflow** → **Run workflow**.
- Wait ~2 minutes. When it finishes (green check), your site is live at:
  `https://YOUR-USERNAME.github.io/chepe-chatter/`

From now on it rebuilds itself **every hour**. You're done with setup.

---

## Part B — Connect your domain `chepe-chatter.news` (after you buy it)

1. Buy the domain (any registrar — Namecheap, Porkbun, Cloudflare, etc.).
2. In your repository: **Settings → Pages → Custom domain**, type `chepe-chatter.news`, Save.
3. At your registrar, add the DNS records GitHub shows you (four "A" records and one
   "CNAME"). GitHub's page has a copy-paste guide. DNS can take a few hours.
4. Tick **Enforce HTTPS** once it appears. Now your site lives at your own address.

---

## Part C — Running it on your own computer (optional, for previewing)

You don't need this to go live, but it's handy to preview changes before publishing.

1. Install Python from https://www.python.org/downloads (tick "Add to PATH" on Windows).
2. Open Terminal (Mac) or Command Prompt (Windows), then:
   ```
   cd path/to/chepe-chatter
   pip install -r requirements.txt
   python build.py
   ```
3. Open the file `site/index.html` in your browser to preview.

---

## Everyday use — how to change things

**Add or remove a news source:** open `feeds.yaml`, copy an existing block, change the
`name`, `url`, `lang`, and `stream`. Save. Commit & push in GitHub Desktop (or just edit
the file directly on github.com and click "Commit changes"). The site updates within the hour.

**Cultural events:** these are now collected **automatically** from GAM Cultural
(`events.py`) on every build — upcoming events, translated and linked, with no work
from you. The `events:` list in `feeds.yaml` is only a fallback used if that source is
ever unreachable. Change how many show with `max_events` in `feeds.yaml`.

**A source stopped showing up?** Its feed URL probably changed. The build skips broken
feeds automatically (the site never breaks), so just find the new feed address and update it.

**Fine-tune what counts as "relevant":** add words to the lists in `classify.py`.

---

## Turning on AI sorting (optional, recommended)

By default the site sorts news with keyword rules. For sharper judgement of
what's relevant to foreigners, you can let Claude do the sorting:

1. Get an API key at https://console.anthropic.com (Settings → API keys). Add a
   little credit — at this site's volume it costs only cents per month.
2. In your repo: **Settings → Secrets and variables → Actions → New repository
   secret.** Name it `ANTHROPIC_API_KEY`, paste the key, Save.
3. Done. The next build detects the key and switches to AI sorting automatically.
   Remove the secret to go back to keyword rules. (Change the model with an
   optional `CLASSIFIER_MODEL` secret.)

## Why the Traffic section uses buttons (not an embedded map)

We tested embedding a live-traffic map, but the self-serve providers don't fit
Costa Rica: **TomTom** has almost no real-time traffic data here (its tiles come
back blank for San José), and **Mapbox** locks live-traffic display behind an
enterprise licence. Only **Google Maps** has good Costa Rica traffic data in an
embeddable form, and that requires a billing-enabled Google Cloud key.

So the Traffic section links straight to Google Maps' traffic layer and Waze —
both have excellent Costa Rica coverage (Waze is what locals actually use), open
in one tap, and cost nothing. The auto-collected road-closures list below them is
the real value-add. If you later want an embedded Google map, it's a small change.

## Upgrading translation quality to DeepL (optional)

The free engine is good. DeepL is better for Spanish. To switch:

1. Sign up at https://www.deepl.com/pro-api (there's a free tier, ~500k chars/month).
2. Copy your API key (free keys end in `:fx` — that's fine, it's auto-detected).
3. In your repo: **Settings → Secrets and variables → Actions → New repository secret.**
   Name it `DEEPL_API_KEY`, paste the key, Save.
4. Done — the next build uses DeepL automatically (the workflow already passes the key).
   Remove the secret to go back to the free engine. Switching engines re-translates
   everything once, then caches as normal.

---

## Sponsors (revenue)

Sponsors are managed in the `sponsors:` list at the bottom of `feeds.yaml` — no
coding. Each sponsor shows as a small "Supported by" card at the foot of the
section(s) you assign it to (`world`, `living`, `sports`, `traffic`, `events`, or
`["all"]`). Give a `name`, a short `tagline_en` and/or `tagline_es` (a missing one
is auto-translated), an optional `logo` image URL, and a `link`.

Assign several sponsors to the same section and they rotate automatically between
hourly builds, so everyone gets fair exposure.

**Available / placeholder spots:** set `placeholder: true` on a sponsor to show an
"this spot is available — book it" card instead. It links to the **Advertise**
section at the bottom of the page.

### Self-service sponsor sign-up (optional but recommended)

Let businesses fill in their own details on the site; the request lands in a
Google Sheet, and you publish it with one tick. No server, no coding.

**How it flows:** business fills the Advertise form → a Google Apps Script adds a
row to your Sheet (with `approved = FALSE`) → you change that cell to `TRUE` → the
next hourly build shows their sponsor card. (You stay in control — nothing goes
live until you approve it, which protects your site from spam.)

**One-time setup (~5 minutes):**

1. Create a Google Sheet. Rename the first tab exactly `Sponsors` and put these
   headers in row 1:
   `timestamp | company | tagline_en | tagline_es | link | logo | section | email | approved`
2. In the Sheet: **Extensions → Apps Script**. Delete the sample, paste the
   contents of `setup/sponsor-form.gs` from this project, and Save.
3. **Deploy → New deployment → Web app.** Set *Execute as: Me* and
   *Who has access: Anyone*. Authorise it, then copy the **Web app URL** (ends `/exec`).
4. **File → Share → Publish to web →** pick the `Sponsors` sheet, format **CSV**,
   Publish, and copy that **CSV URL**.
5. Paste both URLs into `feeds.yaml`: the Web app URL into `sponsor_submit_url`,
   the CSV URL into `sponsor_sheet_csv`. Commit & push.

Done. Businesses can now sign up themselves. To publish one, open the Sheet and set
its `approved` cell to `TRUE`. To take one down, set it back to `FALSE`. A missing
Spanish tagline is auto-translated at build time.

If you skip this setup, the Advertise section just shows an email link instead.

### Payment later

Adding self-service *payment* is possible but needs more parts: Stripe isn't
available in Costa Rica, so you'd use PayPal plus an automation (e.g. Zapier) that
flips `approved` to `TRUE` once someone pays. Ask to add this when you're ready.

Google AdSense is possible later too, but needs original content on the site first
to pass Google's review.

## Built-in extras (nothing to set up)

Every build also generates `robots.txt` and `sitemap.xml` for search engines,
and the page carries the meta tags social media and Google expect — all based
on the `url:` line in `feeds.yaml` (https://chepe-chatter.news).

Stories also stay on the site for up to **48 hours** after their source feed
drops them (a small rolling archive), so the page doesn't "flicker" between
hourly builds — and if every feed is briefly down, the previous stories stay
up instead of the site going empty.

## Weather

The header shows San José's current weather, fetched free from Open-Meteo (no key)
on each hourly build. Nothing to set up; change the location with `weather_lat` /
`weather_lon` in `feeds.yaml`.

---

*Questions or want a new feature? Bring this folder back to me and we'll extend it together.*
