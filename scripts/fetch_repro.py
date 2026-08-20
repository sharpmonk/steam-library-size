"""Reproduction script for Windows crash reports (issue: silent crash mid-fetch).

Fetches ~900 app IDs anonymously - the same shape as a real library scan -
with faulthandler enabled so a hard crash still prints a traceback.
No Steam install needed.
"""

import faulthandler
import sys

faulthandler.enable()

from steam_library_size.sizes import fetch_app_sizes  # noqa: E402

ids = list(range(10, 9010, 10))  # 900 IDs; unknown ones are just skipped
print(f"python {sys.version}", flush=True)
result = fetch_app_sizes(ids, "windows", progress_cb=lambda m: print(m, flush=True))
print(f"OK: {len(result.apps)} apps fetched, {len(result.skipped_appids)} skipped", flush=True)
