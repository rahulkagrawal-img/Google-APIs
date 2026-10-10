#!/usr/bin/env python3
"""
google-marketing-apis: connect Claude Code to Google Search Console, GA4,
Merchant Center (Merchant API v1) and Google Ads (REST API).

All personal files live OUTSIDE the plugin, in a data directory
(default ~/.google-marketing-apis, override with GOOGLE_MARKETING_APIS_DIR):
    client_secret.json   OAuth "Desktop app" client from Google Cloud Console
    token.json           saved login (created by `login`)
    config.json          which property/account IDs to use
    check.off            present = session-start check is switched off

Commands:
    status                         show setup state
    login                          one-time browser login, saves token.json
    discover                       list every property/account your login can see
    config [--gsc-site ...]        save IDs to use (see --help)
    test                           full test of all four services (may open browser)
    check                          session-start check: never opens a browser, never fails
    on | off                       switch the session-start check on/off
    register-merchant ID EMAIL     register your Cloud project with a Merchant Center account
    api METHOD URL [--data JSON] [--header K:V]   authenticated API call, prints JSON
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(os.environ.get("GOOGLE_MARKETING_APIS_DIR") or Path.home() / ".google-marketing-apis")
CLIENT_SECRET = DATA_DIR / "client_secret.json"
TOKEN_FILE = DATA_DIR / "token.json"
CONFIG_FILE = DATA_DIR / "config.json"
OFF_FLAG = DATA_DIR / "check.off"

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/content",
    "https://www.googleapis.com/auth/adwords",
]
# Google Ads REST versions to try, newest first (old versions get sunset).
ADS_API_VERSIONS = ["v25", "v24", "v23", "v22", "v21"]
TIMEOUT = 30
PIP_HINT = "pip install google-auth-oauthlib requests"

try:
    import requests
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    DEPS_OK = True
except ImportError:
    DEPS_OK = False


def require_deps(quiet=False):
    if not DEPS_OK:
        print(f"google-marketing-apis: missing Python packages. Run: {PIP_HINT}")
        sys.exit(0 if quiet else 1)


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except (OSError, ValueError):
        return {}


# ---- Auth -------------------------------------------------------------------
def get_credentials(interactive=True):
    creds = None
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except ValueError:
            creds = None
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())
            return creds
        except Exception as e:
            if not interactive:
                return None
            print(f"Saved login could not be refreshed ({e}); logging in again.")
    if not interactive:
        return None
    return login()


def login():
    if not CLIENT_SECRET.exists():
        sys.exit(f"Missing {CLIENT_SECRET}. Download your OAuth Desktop client JSON from "
                 f"Google Cloud Console and save it there.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    print("Opening browser for Google login...")
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    TOKEN_FILE.write_text(creds.to_json())
    print(f"Login saved to {TOKEN_FILE}")
    return creds


class Client:
    def __init__(self, creds):
        self.creds = creds

    def request(self, method, url, body=None, headers=None, params=None):
        if not self.creds.valid:
            self.creds.refresh(Request())
        h = {"Authorization": f"Bearer {self.creds.token}"}
        if headers:
            h.update(headers)
        return requests.request(method, url, headers=h, json=body, params=params, timeout=TIMEOUT)

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, body, **kw):
        return self.request("POST", url, body=body, **kw)


def api_error(resp):
    try:
        err = resp.json().get("error", {})
        msg = err.get("message") or resp.text
        for d in err.get("details", []):  # Google Ads puts the useful reason here
            for e in d.get("errors", []):
                msg += f" [{e.get('message', '')}]"
    except ValueError:
        msg = resp.text
    return f"HTTP {resp.status_code}: {msg[:500]}"


# ---- Service tests ----------------------------------------------------------
# Each returns (ok, detail). The last line of detail is the one-line summary.
def test_search_console(c, cfg):
    r = c.get("https://www.googleapis.com/webmasters/v3/sites")
    if not r.ok:
        return False, api_error(r)
    sites = [s["siteUrl"] for s in r.json().get("siteEntry", [])]
    if not sites:
        return False, "Connected, but this login has no Search Console properties."
    site = cfg.get("gsc_site_url") or sites[0]
    end = date.today() - timedelta(days=3)  # GSC data lags ~2-3 days
    start = end - timedelta(days=27)
    r = c.post(
        f"https://www.googleapis.com/webmasters/v3/sites/{requests.utils.quote(site, safe='')}/searchAnalytics/query",
        {"startDate": str(start), "endDate": str(end), "dimensions": [], "rowLimit": 1},
    )
    if not r.ok:
        return False, f"Query on {site} failed: {api_error(r)}"
    rows = r.json().get("rows", [])
    clicks = rows[0]["clicks"] if rows else 0
    impressions = rows[0]["impressions"] if rows else 0
    return True, (f"Properties: {sites}\n"
                  f"{site}, {start} to {end}: {clicks:,.0f} clicks, {impressions:,.0f} impressions")


def test_ga4(c, cfg):
    pid = cfg.get("ga4_property_id")
    props = []
    r = c.get("https://analyticsadmin.googleapis.com/v1beta/accountSummaries")
    if r.ok:
        for acct in r.json().get("accountSummaries", []):
            for p in acct.get("propertySummaries", []):
                props.append((p["property"].split("/")[-1], p.get("displayName", "")))
    elif not pid:
        return False, f"Admin API: {api_error(r)}"
    if not pid:
        if not props:
            return False, "Connected, but this login has no GA4 properties."
        pid = props[0][0]
    r = c.post(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{pid}:runReport",
        {
            "dateRanges": [{"startDate": "28daysAgo", "endDate": "yesterday"}],
            "metrics": [{"name": "sessions"}, {"name": "totalUsers"}, {"name": "purchaseRevenue"}],
        },
    )
    if not r.ok:
        return False, f"Data API on property {pid} failed: {api_error(r)}"
    rows = r.json().get("rows", [])
    vals = [m["value"] for m in rows[0]["metricValues"]] if rows else ["0", "0", "0"]
    return True, (f"Properties: {props}\n"
                  f"Property {pid}, last 28 days: {int(vals[0]):,} sessions, {int(vals[1]):,} users, "
                  f"{float(vals[2]):,.2f} purchase revenue")


def test_merchant(c, cfg):
    acct_id = cfg.get("merchant_account_id")
    if not acct_id:
        r = c.get("https://merchantapi.googleapis.com/accounts/v1/accounts", params={"pageSize": 10})
        if not r.ok:
            return False, api_error(r) + merchant_hint(r)
        accts = r.json().get("accounts", [])
        if not accts:
            return False, "Connected, but this login has no Merchant Center accounts."
        acct_id = accts[0]["accountId"]
    r = c.get(f"https://merchantapi.googleapis.com/products/v1/accounts/{acct_id}/products",
              params={"pageSize": 250})
    if not r.ok:
        return False, f"Account {acct_id}: {api_error(r)}" + merchant_hint(r)
    data = r.json()
    n = len(data.get("products", []))
    more = "+" if data.get("nextPageToken") else ""
    return True, f"Account {acct_id}: {n}{more} products"


def merchant_hint(r):
    if "not registered" in r.text:
        return ("\nFix: run `register-merchant <MERCHANT_ID> <YOUR_EMAIL>` once, "
                "then wait ~5 minutes.")
    return ""


def test_google_ads(c, cfg):
    extra = {}
    if cfg.get("ads_login_customer_id"):
        extra["login-customer-id"] = str(cfg["ads_login_customer_id"]).replace("-", "")
    for ver in ADS_API_VERSIONS:
        base = f"https://googleads.googleapis.com/{ver}"
        r = c.get(f"{base}/customers:listAccessibleCustomers", headers=extra)
        if r.status_code == 404:  # version not live (too new or sunset)
            continue
        if not r.ok:
            return False, f"({ver}) {api_error(r)}"
        ids = [n.split("/")[-1] for n in r.json().get("resourceNames", [])]
        if not ids:
            return False, f"({ver}) Connected, but this login has no Google Ads accounts."
        cid = str(cfg.get("ads_customer_id") or ids[0]).replace("-", "")
        query = ("SELECT customer.descriptive_name, customer.currency_code, metrics.impressions, "
                 "metrics.clicks, metrics.cost_micros, metrics.conversions "
                 "FROM customer WHERE segments.date DURING LAST_30_DAYS")
        r = c.post(f"{base}/customers/{cid}/googleAds:search", {"query": query}, headers=extra)
        if not r.ok:
            hint = ""
            if "only approved for use with test accounts" in r.text:
                hint = ("\nFix: apply for Explorer access on the Google Ads API Overview page "
                        "of your Google Cloud project.")
            return False, f"({ver}) Customer {cid}: {api_error(r)}{hint}"
        results = r.json().get("results", [])
        if results:
            cust, m = results[0].get("customer", {}), results[0].get("metrics", {})
            cost = int(m.get("costMicros", 0)) / 1_000_000
            summary = (f"{cust.get('descriptiveName', '')} ({cust.get('currencyCode', '')}), last 30 days: "
                       f"{int(m.get('impressions', 0)):,} impr, {int(m.get('clicks', 0)):,} clicks, "
                       f"{cost:,.2f} cost, {float(m.get('conversions', 0)):,.1f} conv")
        else:
            summary = "no activity in the last 30 days"
        return True, f"API {ver}. Accessible customers: {ids}\nCustomer {cid}: {summary}"
    return False, "No live Google Ads API version found; update ADS_API_VERSIONS in the plugin."


TESTS = [
    ("Search Console", test_search_console),
    ("GA4", test_ga4),
    ("Merchant Center", test_merchant),
    ("Google Ads", test_google_ads),
]


def run_tests(c, compact):
    cfg = load_config()
    results = []
    for name, fn in TESTS:
        try:
            ok, detail = fn(c, cfg)
        except requests.RequestException as e:
            ok, detail = False, f"Network error: {e}"
        results.append(ok)
        if compact:
            line = detail.strip().splitlines()[-1] if ok else detail.strip().replace("\n", " ")
            print(f"  {name}: {'OK' if ok else 'FAILED'} - {line[:300]}")
        else:
            print(f"{name}: {'PASS' if ok else 'FAIL'}")
            for ln in detail.splitlines():
                print(f"    {ln}")
            print()
    return results


# ---- Commands ---------------------------------------------------------------
def cmd_status(_):
    cfg = load_config()
    print(f"Data directory:     {DATA_DIR}")
    print(f"client_secret.json: {'found' if CLIENT_SECRET.exists() else 'MISSING'}")
    print(f"token.json:         {'found' if TOKEN_FILE.exists() else 'missing (run login)'}")
    print(f"Python packages:    {'ok' if DEPS_OK else 'MISSING - ' + PIP_HINT}")
    print(f"Session-start check: {'OFF' if OFF_FLAG.exists() else 'ON'}")
    print("Configured IDs:     " + (json.dumps(cfg) if cfg else "none (first available is used)"))


def cmd_login(_):
    require_deps()
    login()


def cmd_check(_):
    if OFF_FLAG.exists():
        return
    require_deps(quiet=True)
    if not CLIENT_SECRET.exists():
        print("Google APIs (google-marketing-apis plugin): not set up yet. Run /google-apis-setup.")
        return
    creds = get_credentials(interactive=False)
    if not creds:
        print("Google APIs (google-marketing-apis plugin): not logged in or login expired. "
              "Run /google-apis login.")
        return
    print("Google APIs (google-marketing-apis plugin) connection check:")
    try:
        run_tests(Client(creds), compact=True)
    except Exception as e:  # never break session start
        print(f"  check failed: {e}")


def cmd_test(_):
    require_deps()
    creds = get_credentials(interactive=True)
    results = run_tests(Client(creds), compact=False)
    print("Summary: " + ", ".join(f"{n}: {'OK' if ok else 'FAILED'}" for (n, _), ok in zip(TESTS, results)))
    sys.exit(0 if all(results) else 1)


def cmd_on(_):
    OFF_FLAG.unlink(missing_ok=True)
    print("Session-start check: ON")


def cmd_off(_):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OFF_FLAG.touch()
    print("Session-start check: OFF (login and API access are unchanged)")


def cmd_discover(_):
    require_deps()
    c = Client(get_credentials(interactive=True))
    out = {}
    r = c.get("https://www.googleapis.com/webmasters/v3/sites")
    out["search_console_sites"] = ([s["siteUrl"] for s in r.json().get("siteEntry", [])]
                                   if r.ok else api_error(r))
    r = c.get("https://analyticsadmin.googleapis.com/v1beta/accountSummaries")
    out["ga4_properties"] = ([{"id": p["property"].split("/")[-1], "name": p.get("displayName", "")}
                              for a in r.json().get("accountSummaries", [])
                              for p in a.get("propertySummaries", [])] if r.ok else api_error(r))
    r = c.get("https://merchantapi.googleapis.com/accounts/v1/accounts", params={"pageSize": 50})
    out["merchant_accounts"] = ([{"id": a["accountId"], "name": a.get("accountName", "")}
                                 for a in r.json().get("accounts", [])] if r.ok
                                else api_error(r) + merchant_hint(r))
    ads = api_error(r)
    for ver in ADS_API_VERSIONS:
        r = c.get(f"https://googleads.googleapis.com/{ver}/customers:listAccessibleCustomers")
        if r.status_code == 404:
            continue
        if not r.ok:
            ads = api_error(r)
            break
        ads = []
        for n in r.json().get("resourceNames", []):
            cid = n.split("/")[-1]
            q = c.post(f"https://googleads.googleapis.com/{ver}/customers/{cid}/googleAds:search",
                       {"query": "SELECT customer.descriptive_name, customer.manager, customer.status FROM customer"})
            if q.ok and q.json().get("results"):
                cu = q.json()["results"][0]["customer"]
                ads.append({"id": cid, "name": cu.get("descriptiveName", ""),
                            "manager": cu.get("manager", False), "status": cu.get("status", "")})
            else:
                ads.append({"id": cid, "note": api_error(q)[:160]})
        break
    out["google_ads_customers"] = ads
    print(json.dumps(out, indent=2))


def cmd_config(a):
    cfg = load_config()
    for key in ("gsc_site_url", "ga4_property_id", "merchant_account_id",
                "ads_customer_id", "ads_login_customer_id"):
        val = getattr(a, key)
        if val is not None:
            if val == "":
                cfg.pop(key, None)
            else:
                cfg[key] = val.replace("-", "") if key.startswith("ads_") else val
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    print(json.dumps(cfg, indent=2))


def cmd_register_merchant(a):
    require_deps()
    c = Client(get_credentials(interactive=True))
    r = c.post(f"https://merchantapi.googleapis.com/accounts/v1/accounts/{a.account_id}"
               f"/developerRegistration:registerGcp", {"developerEmail": a.email})
    print(json.dumps(r.json(), indent=2) if r.ok else api_error(r))
    if r.ok:
        print("Registered. Google says to wait ~5 minutes before calling the Merchant API.")
    sys.exit(0 if r.ok else 1)


def cmd_api(a):
    require_deps()
    c = Client(get_credentials(interactive=False) or sys.exit("Not logged in. Run: login"))
    headers = {}
    for h in a.header or []:
        k, _, v = h.partition(":")
        headers[k.strip()] = v.strip()
    body = json.loads(a.data) if a.data else None
    r = c.request(a.method.upper(), a.url, body=body, headers=headers)
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(r.text)
    sys.exit(0 if r.ok else 1)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("status", cmd_status), ("login", cmd_login), ("check", cmd_check),
                     ("test", cmd_test), ("on", cmd_on), ("off", cmd_off), ("discover", cmd_discover)]:
        sub.add_parser(name).set_defaults(fn=fn)
    s = sub.add_parser("config", help="save IDs (pass \"\" to clear one)")
    s.add_argument("--gsc-site", dest="gsc_site_url")
    s.add_argument("--ga4-property", dest="ga4_property_id")
    s.add_argument("--merchant-account", dest="merchant_account_id")
    s.add_argument("--ads-customer", dest="ads_customer_id")
    s.add_argument("--ads-login-customer", dest="ads_login_customer_id")
    s.set_defaults(fn=cmd_config)
    s = sub.add_parser("register-merchant")
    s.add_argument("account_id")
    s.add_argument("email")
    s.set_defaults(fn=cmd_register_merchant)
    s = sub.add_parser("api")
    s.add_argument("method")
    s.add_argument("url")
    s.add_argument("--data", help="JSON request body")
    s.add_argument("--header", action="append", help="extra header, e.g. login-customer-id:1234567890")
    s.set_defaults(fn=cmd_api)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
