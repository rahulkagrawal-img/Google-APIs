# google-marketing-apis: a Claude Code plugin

Connect Claude Code to **Google Search Console, Google Analytics 4, Google Merchant Center and Google Ads**. It uses your own Google Cloud project, so it's free, and no third-party service ever sees your data.

Once installed, you can ask Claude things like:
- "Which search queries lost the most clicks this month?"
- "What were GA4 revenue and sessions by channel over the last 28 days?"
- "Which Merchant Center products are disapproved, and why?"
- "Which Google Ads campaigns are spending without converting?"

## What's included

| Part | What it does |
|---|---|
| `/google-apis-setup` | A guided first-time setup: Google Cloud project, login, choosing your accounts, and a connection test. |
| `/google-apis on \| off \| status \| test \| login` | Switches the startup check on or off, shows status, re-tests or logs in again. |
| `google-marketing-data` skill | Claude uses it automatically when you ask about your SEO, analytics, product feed or ads data. |
| Session-start check | When each session starts, it prints one line per service (OK or FAILED, plus headline numbers). It never opens a browser and never blocks the session. |

It's read-first. Claude asks before making any change to your accounts.

---

## Requirements
- Claude Code, run in the CLI or the desktop app. On Windows you also need Git for Windows, which Claude Code uses for bash.
- Python 3.9 or newer.
- These Python packages:
  ```bash
  pip install google-auth-oauthlib requests
  ```
- A Google account with access to the products you want to connect.

## Install

Option 1: from GitHub, once this folder is pushed to a repo.
```
/plugin marketplace add YOUR-GITHUB-USER/google-marketing-tools
/plugin install google-marketing-apis@google-marketing-tools
```

Option 2: from a local folder.
```
/plugin marketplace add /path/to/google-marketing-tools
/plugin install google-marketing-apis@google-marketing-tools
```

Restart Claude Code, then run **`/google-apis-setup`**. Claude walks you through everything below.

---

## Manual setup (what `/google-apis-setup` guides you through)

### 1. Create a Google Cloud project (free, no billing account needed)
1. Go to [console.cloud.google.com](https://console.cloud.google.com). In the project picker, choose **New Project**.
2. Under **APIs & Services → Library**, enable these five APIs:
   - Google Search Console API
   - Google Analytics Data API
   - Google Analytics Admin API
   - **Merchant API**. The old "Content API for Shopping" was shut down on 18 Aug 2026.
   - Google Ads API

### 2. Set up the OAuth consent screen (Google Auth Platform)
1. Choose **External** and fill in an app name and your email.
2. Under **Audience → Test users**, add your Google account.
3. Under **Data Access**, add these scopes:
   - `https://www.googleapis.com/auth/webmasters.readonly`
   - `https://www.googleapis.com/auth/analytics.readonly`
   - `https://www.googleapis.com/auth/content`
   - `https://www.googleapis.com/auth/adwords`
4. Go to **Clients → Create client → Desktop app** and download the JSON file.
5. Go to **Audience → Publish app**. Apps left in Testing mode lose their login every 7 days. For personal use you don't need Google's verification, but you'll click past an "unverified app" warning once.

### 3. Get Google Ads API access
Since 9 Sept 2026, Google Ads API access belongs to your **Cloud project**. Developer tokens and the API Center page in Google Ads are no longer used.
1. In Cloud Console, open the **Google Ads API Overview** page.
2. Apply for **Explorer** access. It covers your real accounts, up to 2,880 operations a day, and is usually approved quickly.
3. Basic and Standard access need brand verification. You only need them for heavy use.

### 4. Save your files
All personal files live **outside the plugin**, in `~/.google-marketing-apis/`. On Windows that's `C:\Users\<you>\.google-marketing-apis\`. To use a different folder, set the `GOOGLE_MARKETING_APIS_DIR` environment variable.

| File | What it is |
|---|---|
| `client_secret.json` | The OAuth client file you downloaded. Rename it to this. |
| `token.json` | Your saved login. It's created when you log in. |
| `config.json` | The account IDs to use. It's created by `config`. |
| `check.off` | Present when the startup check is switched off. |

### 5. Log in, pick accounts, test
In the commands below, `SCRIPT` stands for `<plugin folder>/scripts/google_apis.py`. Inside Claude, the skills run these for you.
```bash
python SCRIPT login
```
```bash
python SCRIPT discover
```
```bash
python SCRIPT config --gsc-site "sc-domain:example.com" --ga4-property 123456789 --merchant-account 1234567 --ads-customer 1234567890
```
```bash
python SCRIPT test
```

### 6. Merchant Center: register your project once
The Merchant API requires every Cloud project to be registered with each Merchant Center account. If the test reports "GCP project … is not registered", run this, then wait about 5 minutes:
```bash
python SCRIPT register-merchant YOUR_MERCHANT_ID you@example.com
```

---

## Script reference
```
status                         show setup state
login                          one-time browser login
discover                       list every property and account your login can see
config --gsc-site ... --ga4-property ... --merchant-account ... --ads-customer ... [--ads-login-customer MCC_ID]
test                           full test of all four services
check                          the session-start check (never opens a browser)
on | off                       switch the session-start check on or off
register-merchant ID EMAIL     register your Cloud project with a Merchant Center account
api METHOD URL [--data JSON] [--header K:V]   authenticated API call that prints JSON
```

## Troubleshooting

| Message | Fix |
|---|---|
| `not logged in or login expired` | Run `/google-apis login`. If this happens weekly, your consent screen is still in **Testing**, so publish it. |
| Merchant: `GCP project … is not registered` | Run `register-merchant` (step 6). |
| Ads: `only approved for use with test accounts` | Explorer access hasn't been approved yet (step 3). |
| Ads: `AUTHORIZATION_ERROR` after upgrading access | This is a known Google issue from Sept 2026. Google's workaround is to apply for Explorer on a new Cloud project. |
| Ads: `CUSTOMER_NOT_ENABLED` | That account is cancelled or was never set up. Choose another ID with `config --ads-customer`. |
| Ads: `No live Google Ads API version found` | Google has retired the versions this plugin knows. Update `ADS_API_VERSIONS` in `scripts/google_apis.py`. |
| `missing Python packages` | Run `pip install google-auth-oauthlib requests`. |
| Windows: `Python was not found; run without arguments to install from the Microsoft Store` | `python` is pointing at a Store placeholder. Use `py` instead, or turn off the python aliases in Settings → Apps → Advanced app settings → App execution aliases. The startup check already falls back to `py`. |

## Security
- `client_secret.json` and `token.json` give access to your Google accounts. **Never commit, share or upload them.** They're stored outside the plugin and outside your projects for exactly this reason.
- To revoke access at any time, go to [myaccount.google.com/permissions](https://myaccount.google.com/permissions) and delete `token.json`.
- The login asks for read-only access to Search Console and Analytics. Merchant Center and Google Ads have no read-only scope, so Claude is told to ask before any change.

## Uninstall
```
/plugin uninstall google-marketing-apis@google-marketing-tools
```
Then delete `~/.google-marketing-apis/` if you no longer need the login.

## License
MIT
