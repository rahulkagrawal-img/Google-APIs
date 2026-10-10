---
name: google-apis-setup
description: Guided first-time setup for connecting Google Search Console, GA4, Merchant Center and Google Ads to Claude Code through the user's own Google Cloud project. Use when the user wants to set up, connect or reconnect these Google APIs, or when the google-marketing-apis check says "not set up yet".
---

# Google APIs setup

Walk the user through setup one stage at a time. Check each stage before moving to the next.

- **Script:** `${CLAUDE_PLUGIN_ROOT}/scripts/google_apis.py`, run with `python3`, `python` or `py`, whichever really runs Python. On Windows, `python` and `python3` may be Store placeholders, and `py` usually works.
- **Data directory:** the user's personal files go here. It is `~/.google-marketing-apis` unless `GOOGLE_MARKETING_APIS_DIR` is set. Run `google_apis.py status` to see the exact path.

## Stage 0: Check the starting point
Run `google_apis.py status`.
- If the Python packages are missing, ask the user whether you may run `pip install google-auth-oauthlib requests`, then run it.
- Skip any stage that `status` shows is already done.

## Stage 1: Google Cloud project (the user does this in their browser)
Give the user these steps. Everything here is free, and no billing account is needed.
1. Go to console.cloud.google.com and create a new project.
2. Under APIs & Services → Library, enable these five APIs:
   - Google Search Console API
   - Google Analytics Data API
   - Google Analytics Admin API
   - Merchant API (**not** "Content API for Shopping", which was shut down in August 2026)
   - Google Ads API
3. Set up the OAuth consent screen (Google Auth Platform):
   - Choose **External** and fill in the app name and email.
   - Under Audience → Test users, add the user's own Google account.
   - Under Data Access, add these scopes:
     - `.../auth/webmasters.readonly`
     - `.../auth/analytics.readonly`
     - `.../auth/content`
     - `.../auth/adwords`
4. Go to Clients → Create client, choose **Desktop app**, and download the JSON file.
5. Go to Audience and click **Publish app**. In Testing mode, the login expires every 7 days. For personal use, full verification isn't needed.
6. Find the Google Ads API Overview page in the Cloud project and apply for **Explorer** access. Since Sept 2026, access belongs to the Cloud project, and developer tokens are no longer used.

## Stage 2: Client file
Ask the user to save the downloaded JSON as `client_secret.json` in the data directory. You can copy it there if they tell you where the file is.
- Never print the file's contents. To confirm it's valid, only check that the file has an `installed` key.

## Stage 3: Login
Run `google_apis.py login` in the background. Tell the user:
- Pick the Google account that has access to all four products.
- On "Google hasn't verified this app", click Advanced, then Go to (app name).
- Tick all permissions.

Wait until the script reports that the login was saved.

## Stage 4: Choose accounts
1. Run `google_apis.py discover` and show the user what was found.
2. If any service lists more than one option, ask which one they want.
3. Save their choices with `google_apis.py config --gsc-site ... --ga4-property ... --merchant-account ... --ads-customer ...`.
4. Add `--ads-login-customer` only if they reach the Ads account through a manager (MCC) account.

## Stage 5: Test and fix
Run `google_apis.py test`. Common failures:
- **Merchant "GCP project ... is not registered"**: ask the user for permission and for the email to use as the developer contact. Then run `google_apis.py register-merchant <MERCHANT_ID> <EMAIL>`, wait about 5 minutes, and test again. This registration changes the user's Merchant Center account, so always ask first.
- **Google Ads "only approved for use with test accounts"**: Explorer access hasn't been approved yet. The user applies or waits, then you test again.
- **Google Ads AUTHORIZATION_ERROR after an upgrade**: this is a known Google issue. Google's workaround is to apply for Explorer on a new Cloud project.
- **Accounts that say "not enabled or deactivated"**: those are old or cancelled accounts. Choose a different ID.

## Finish
Tell the user:
- The connection check now runs at the start of every session, and `/google-apis off` turns it off.
- The google-marketing-data skill lets them ask for reports in plain language.
- `client_secret.json` and `token.json` give access to their accounts and must never be shared.
