---
name: google-apis
description: Switch the session-start Google API check on or off, show setup status, log in again, or run a full connection test. Usage - /google-apis on | off | status | test | login
disable-model-invocation: true
---

Manage the google-marketing-apis plugin. The plugin's script is `${CLAUDE_PLUGIN_ROOT}/scripts/google_apis.py`. Run it with the first of `python3`, `python` or `py` that actually works. On Windows, `python` and `python3` can be Microsoft Store placeholders that only print "Python was not found"; in that case use `py`.

Act on the argument `$ARGUMENTS` (use `status` if it is empty):

| Argument | Run | Then |
|---|---|---|
| `on` | `google_apis.py on`, then `google_apis.py check` | Report one line per service. |
| `off` | `google_apis.py off` | Confirm that new sessions will skip the check. The login and API access are unchanged. |
| `status` | `google_apis.py status` | Summarise the result in a few lines. |
| `test` | `google_apis.py test` | Report PASS/FAIL per service. For each failure, give the "Fix:" line the script prints. |
| `login` | `google_apis.py login`, run in the background | Tell the user to finish the Google login in the browser tab that opens: click Advanced, then Go to (app name) on the "unverified app" warning, then allow all permissions. |

If `status` shows that `client_secret.json` is missing, point the user to `/google-apis-setup`.

Keep replies short. Never print or open `token.json` or `client_secret.json`.
