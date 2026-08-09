# Feature Wishlist

Ideas for **home / power-user** improvements over time. Not a commitment or roadmap — priority is a guide for what would help most next.

Audience: people who want a proper restic app, not an enterprise Veeam/Acronis replacement.

---

## High value (users will feel this)

1. **Backup success at a glance**
   - Email / toast / tray alert when the last backup failed and the app isn’t open
   - Simple health badge: “all jobs OK in the last 24h”

2. **Verify / restore drills**
   - Guided “restore one file” flow
   - Periodic `restic check` reminder so users trust their backups

3. **Exclude presets**
   - One-click excludes for common junk (Windows Temp / caches, `node_modules`, browser caches, etc.)

4. **First-run wizard**
   - Create local repo → pick folders → schedule → test connection
   - Especially important for non-restic users

5. **Finish SFTP / HTTPS wiring** ✅ Done
   - Shared `build_repo_env` / `repo_restic_prefix` (and scheduled-script helpers) now cover backup, restore, check, forget, prune, unlock, copy, stats, browse, and retention schedules
   - Remaining **restic** limit (not app-only): copy between two HTTPS repos with different HTTP Basic Auth credentials — documented in README

---

## Strong differentiators vs “just restic CLI”

6. **Append-only / ransomware guidance**
   - In-app tip explaining append-only keys and immutable / offline storage
   - Link or short how-to (full Object Lock UI can wait)

7. **Second copy (3-2-1 for home users)**
   - First-class pattern: also back up to USB / a second repository

8. **Dry-run backup**
   - Show what would be included before the first real run

9. **Password / key recovery UX**
   - Clear warning: lose the repo password → lose the data
   - Optional printable recovery sheet
   - Export encrypted settings backup

---

## Nice later (don’t block a solid 1.0)

10. Cloud backends (S3 / B2 / etc.) with proper credential forms  
11. Richer snapshot tags / search filters; compare jobs  
12. Bandwidth limits / schedule windows (“only after 11pm”)  
13. Linux / macOS scheduling parity (if those platforms matter)  
14. Auto-update check for the app + restic version warning  

---

## Practical “might need” (outside big features)

- Backup / restore of `restic_settings.json` (and a note that passwords are machine-bound)
- Crash / log export for support
- Clear docs for NAS SSH keys + REST server (started in-app + README)
- One sample job or screenshots in the README for trust

---

## Intentionally not chasing (wrong audience)

- Full image / bare-metal backup like Veeam or Acronis
- Central multi-PC enterprise console
- Compliance / audit report suites

---

## Suggested next three

If only a few items are picked next:

1. **First-run wizard**  
2. **Failed-backup alerting when the app is closed**  
3. **Exclude presets**  

Those best support the “I don’t have to think about restic” story for home users.
