---
name: google-marketing-data
description: Query live data from Google Search Console, Google Analytics 4, Google Merchant Center and Google Ads through the google-marketing-apis plugin. Use for SEO queries, clicks, impressions, rankings, GA4 sessions, traffic, revenue and conversions, product and feed status, disapprovals, and Google Ads campaigns, spend, CPC, ROAS and search terms.
---

# Querying Google marketing data

All calls go through the plugin script. It handles login and token refresh, so the token never appears in the conversation.

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/google_apis.py" api METHOD URL [--data 'JSON'] [--header 'name:value']
```
- Use `python` or `py` instead of `python3` if needed. On Windows, `py` is the most reliable.
- The output is the JSON response, and the exit code is 1 on an HTTP error.
- On Windows PowerShell, pass `--data` through a here-string or a variable so the quotes survive.
- To find the user's IDs, run `google_apis.py status` and read the "Configured IDs" line. The keys are `gsc_site_url`, `ga4_property_id`, `merchant_account_id`, `ads_customer_id` and `ads_login_customer_id`. If an ID is missing, run `google_apis.py discover`.
- If you get "Not logged in", tell the user to run `/google-apis login`.

## Rules
- **Reads are fine. Ask before any write.** That includes changing campaigns, bids, budgets or keywords, inserting or deleting products, and changing account settings. State exactly what will change and wait for a clear yes.
- **Search Console:**
  - Data lags 2–3 days.
  - It returns at most 25,000 rows per request, so page with `startRow`.
  - A site URL looks like `sc-domain:example.com` and must be URL-encoded inside the path.
- **Google Ads:**
  - Money comes back in micros: divide by 1,000,000.
  - Some fields are 64-bit numbers and come back as strings.
  - Explorer access is capped at 2,880 operations a day, so don't loop over hundreds of calls.
  - If the account sits under a manager account, add `--header login-customer-id:<MCC_ID>`.
- Summarise the results for the user. Don't dump raw JSON unless they ask for it.

## Endpoints

### Search Console
```
POST https://www.googleapis.com/webmasters/v3/sites/{ENCODED_SITE}/searchAnalytics/query
{"startDate":"2026-09-01","endDate":"2026-09-30","dimensions":["query"],"rowLimit":100,"orderBy":[{"field":"clicks","descending":true}]}
```
- Dimensions: `query`, `page`, `country`, `device`, `date` and `searchAppearance`.
- Filters go in `"dimensionFilterGroups":[{"filters":[{"dimension":"page","operator":"contains","expression":"/sarees"}]}]`.
- URL inspection: `POST https://searchconsole.googleapis.com/v1/urlInspection/index:inspect` with `{"inspectionUrl":"...","siteUrl":"..."}`.

### GA4 Data API
```
POST https://analyticsdata.googleapis.com/v1beta/properties/{ID}:runReport
{"dateRanges":[{"startDate":"28daysAgo","endDate":"yesterday"}],
 "dimensions":[{"name":"sessionDefaultChannelGroup"}],
 "metrics":[{"name":"sessions"},{"name":"purchaseRevenue"},{"name":"transactions"}],
 "orderBys":[{"metric":{"metricName":"sessions"},"desc":true}],"limit":50}
```
- Common dimensions: `date`, `sessionSourceMedium`, `landingPage`, `itemName`, `deviceCategory` and `country`.
- Common metrics: `activeUsers`, `ecommercePurchases`, `addToCarts`, `itemRevenue` and `conversions`.
- To see every valid dimension and metric: `GET .../properties/{ID}/metadata`.

### Merchant API v1
- Products: `GET https://merchantapi.googleapis.com/products/v1/accounts/{ID}/products?pageSize=250` (page with `pageToken`).
- Product status and disapprovals are in each product's `productStatus.itemLevelIssues`.
- Performance reports:
  ```
  POST https://merchantapi.googleapis.com/reports/v1/accounts/{ID}/reports:search
  {"query":"SELECT offer_id, title, clicks, impressions FROM product_performance_view WHERE date BETWEEN '2026-09-01' AND '2026-09-30' ORDER BY clicks DESC LIMIT 50"}
  ```

### Google Ads (REST; use the version `test` reports, e.g. v24)
```
POST https://googleads.googleapis.com/v24/customers/{CUSTOMER_ID}/googleAds:search
{"query":"SELECT campaign.name, campaign.status, metrics.cost_micros, metrics.clicks, metrics.conversions, metrics.conversions_value FROM campaign WHERE segments.date DURING LAST_30_DAYS ORDER BY metrics.cost_micros DESC"}
```
Useful resources to query with GAQL:
- Search terms: `search_term_view`.
- Keywords: `keyword_view` with `ad_group_criterion.keyword.text`.
- Products in Shopping and Performance Max: `shopping_performance_view` with `segments.product_item_id`.
- Conversion actions: `conversion_action`, with `segments.conversion_action_name` on `campaign`.
- Asset groups: `asset_group`.
