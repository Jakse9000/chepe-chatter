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
| `classify.py` | The rules that decide "is this relevant to foreigners?" Edit later to fine-tune. |
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

## Upgrading translation quality to DeepL (later, optional)

The free engine is good. DeepL is better for Spanish. When you want to switch:

1. Sign up at https://www.deepl.com/pro-api (there's a free tier).
2. Copy your API key.
3. In your repo: **Settings → Secrets and variables → Actions → New repository secret.**
   Name it `DEEPL_API_KEY`, paste the key.
4. In `.github/workflows/build.yml`, remove the two `#` comment marks in front of the
   `env:` and `DEEPL_API_KEY:` lines. Commit. Done — it now uses DeepL automatically.

---

## When you're ready to think about revenue

The sponsor slot already exists in the design (the dashed box under "Living here"). When
you have steady readers, replace its placeholder text with a real sponsor in
`templates/index.html`. The project plan lists the non-intrusive options in priority order.

---

*Questions or want a new feature? Bring this folder back to me and we'll extend it together.*
