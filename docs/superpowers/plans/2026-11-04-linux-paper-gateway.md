# Linux Paper Gateway Implementation Plan

Goal: deliver an independently tested single-attempt launcher and deploy without login.
Architecture: stdlib-only Python validation and process supervisor, invoking the original IBC Java entry point with external configuration and a reviewed file manifest.
Spec: ../specs/2026-11-04-linux-paper-gateway-design.md

- [ ] Add failing tests for config safety, redaction, non-launching checks, manifest tampering, process/lease exclusion, timeout and explicit activation.
- [ ] Implement `competition_tools.linux_gateway_launcher` and a public example configuration; keep Windows behavior unchanged.
- [ ] Synchronize English and Chinese operations guidance. Run root validation and review the branch.
- [ ] Merge checked PR, deploy stable code and IBC externally, and run check/dry-run only. Record retention evidence.

Review focus: special characters in credentials must remain in Java Properties; symlinks and weak permissions fail closed; occupied sessions/leases are not taken over; timeouts retain recoverable state; no local test claims actual broker compatibility.
