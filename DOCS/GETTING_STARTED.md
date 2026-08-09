# Getting started with Restic Desktop

This guide walks through a first successful backup and restore. You only need about ten minutes.

## 1. Install and open the app

**From a release (recommended for most users):** download the build from [GitHub Releases](https://github.com/Dallustallus/restic_manager/releases) and run it. You do not need Python.

**From source (developers):**

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
pip install -r requirements.txt
python restic_manager.py
```

## 2. Make sure restic is available

Restic Desktop drives [restic](https://restic.net/); it does not replace it.

1. Open **Settings → Dependencies**.
2. Confirm restic is found, or install / set the path there.
3. Or install restic yourself from [restic.net](https://restic.net/) and ensure it is on your `PATH`.

Without a working restic binary, backups and restores will fail.

## 3. Add a repository

A repository is where encrypted backup data is stored (local folder, SFTP, or HTTPS REST server).

1. Open **Repositories**.
2. Add a repository (local is simplest for a first test).
3. Choose or create a strong **repository password** and store it somewhere safe — without it you cannot restore.
4. Initialize the repository when prompted, then test the connection.

Tips:

- Prefer one repository per backup destination (for example one NAS share), and use **jobs / tags** to separate workloads.
- For SFTP, use SSH key login; interactive password prompts will not work for scheduled jobs.
- HTTP Basic Auth (HTTPS REST) is separate from the repository password that encrypts your data.

## 4. Create a backup job

1. Open **Backup Jobs**.
2. Use the **Backup Wizard** (recommended first time), or the advanced job editor.
3. Pick the repository, the folders to back up, and any excludes/tags you need.
4. Leave **Skip snapshot if unchanged** enabled unless you have a reason not to (avoids empty snapshots when nothing changed).
5. Optionally enable a schedule (Windows Task Scheduler from the wizard / job settings).

Save the job, then run it once from the Backup Jobs page and watch **Logs** if anything fails.

## 5. Confirm it worked

1. Open **Snapshots** (or the Dashboard) and confirm a new snapshot appeared.
2. Open **Restore**.
3. Choose the repository and snapshot, pick a safe test folder as the restore target (not your live files on the first try).
4. Restore a small set of files and check they look correct.

Doing a test restore early is the best way to trust your setup.

## What to do next

| Goal | Where |
|------|--------|
| Automatic backups | Job schedule (Windows) or CLI `--run-job` / cron on Linux |
| Keep repo size under control | **Retention** — dry-run first, then apply |
| Check backup freshness | **Dashboard** / health scoring |
| Browse or search files | **Restore** (Restore / Find files modes) |
| Move the app to another PC | **Settings → Backup Settings** (include history DB if you want run history); re-enter repo passwords on the new machine |

## Common issues

| Problem | Fix |
|---------|-----|
| Restic not found | Settings → Dependencies, or install from https://restic.net/ |
| Backup “locked” | Unlock from repository actions (interrupted runs can leave locks) |
| Scheduled backup did not log | Confirm the scheduled script can reach the app / Python and write `restic_history.db` |
| Forgot repository password | It cannot be recovered from this app — only from your own password store |

More detail: [README](../README.md) (backends, data files, CLI, troubleshooting).
