# Linux Paper Gateway

Provide an explicit, single-attempt Linux launcher for an independently installed offline Gateway and IBC 3.24.2. Reuse the external owner-only IBC INI; credentials never enter command arguments or output. Manual mobile authentication remains necessary.

Alternatives were manual Gateway login, upstream IBC shell scripts, and an independent single-attempt launcher. The selected launcher preserves the official installation and avoids upstream script renames, restart loops and session-file deletion. It invokes the same Java entry point and VM configuration as upstream.

Separate read-only `check`/`dry-run` from explicitly authorized `start`. Validate owner-only configuration, settings and logs, paths, manifest hashes, Paper/read-only INI settings and existing Java/Gateway processes. Use an exclusive persistent lease, with a second preflight after acquisition. Timeout never kills or retries the child; retain the lease for manual inspection. No boot tasks, daily restart or orders. Configuration and logs stay outside source. Desktop presence and local checks do not prove authentication or API readiness. True broker verification is a separate supervised step.
