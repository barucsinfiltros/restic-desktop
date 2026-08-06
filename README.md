# Restic Backup Manager

A PyQt6 GUI application for managing Restic backups with a familiar interface similar to your Network Management Tool.

## What's New in Recent Updates

### Repository backends — Local, SFTP, HTTPS ✨ NEW
- 📁 **Local folder**: Browse and pick a path on disk / external drive
- 🔐 **SFTP (NAS / remote)**: Host, port, username, remote path, optional SSH private key
  - Restic requires SSH **key** login (not an interactive SSH password)
  - In-dialog tip covers `ssh-keygen`, copying the public key to the NAS, and testing `ssh`
- 🌐 **HTTPS (REST server)**: URL for restic REST server (or compatible endpoint)
  - HTTP auth modes: **Anonymous**, **Username + password**, or **Password only**
  - HTTP credentials are separate from the **repository password** (backup encryption)
  - Passed to restic via `RESTIC_REST_USERNAME` / `RESTIC_REST_PASSWORD`
- 🎨 Theme combo: dark themes, separator, then light themes
- Combo selection contrast fixed (selected item stays readable)

### Repository Health Status ✨ NEW
- 🟢 **Status column**: Configured Repositories shows ● Healthy / ● Warning / ● Unreachable / ● Unknown
- 🔍 **Real checks**: Status comes from `restic snapshots --latest 1` (not from merely saving the form)
- ⚠️ **Warning**: Last successful check older than 7 days
- ⋯ **Actions menu**: Check connection, Edit, Delete (replaces inline Edit | Delete links)
- 🎨 **Jobs-style table**: Softer headers, muted secondary columns, icon chips matching Recent Backup Jobs
- 🕒 **Last Checked**: Updated only when a check (or dialog Test) actually runs

### SQLite History Store ✨ NEW
- 🗄️ **Job & dashboard history**: Append-only SQLite database (`restic_history.db`) beside `restic_settings.json`
- ⏱️ **Run duration**: Every GUI, CLI (`--run-job`), and Windows scheduled backup records start/finish, duration, success/fail, and a short error summary
- 📊 **Recent Backup Jobs**: New **Duration** column (`HH:MM:SS`); **Status** comes from the last recorded run (Success / Failed / Scheduled / Ready) — failed runs no longer look like Success
- 💾 **Dashboard cache**: Refresh samples per-repo size/snapshot counts into `repo_stats` and upserts a `dashboard_cache` blob so the next launch paints cards and charts immediately
- 🔁 **Scheduled Windows tasks**: Generated PowerShell scripts call `python restic_manager.py --record-job-run …` after restic exits (no SQLite in PowerShell)
- 🛠️ **Stdlib only**: Uses Python’s built-in `sqlite3` (`core/history_db.py`) — no new package dependencies
- 📌 **Settings stay JSON**: Config remains in `restic_settings.json`; history/time-series data lives in the DB
- 🖱️ **Jobs context menu**: Right-click a Recent Backup Jobs row for Run, Edit, Copy snapshot ID, Last run details

### Automated Backup Scheduling ✨ NEW
- 📅 **Task Scheduler Integration**: Create scheduled tasks to automatically run backup jobs
- 🪟 **Windows Task Scheduler**: One-click scheduled backup creation with `schtasks.exe`
- ⏰ **Flexible Scheduling**: Choose Daily, Weekly, or Monthly backup runs
- 🕐 **Custom Time Selection**: Pick exact time for backups (e.g., 2:00 AM for off-hours)
- 📆 **Day Selection**: Specify which days to run (Weekly) or day of month (Monthly)
- ⚙️ **Independent Operation**: Scheduled tasks run restic directly; a short `--record-job-run` call logs history afterward
- 🔒 **Secure Password Storage**: Uses Windows DPAPI to encrypt repository passwords
- 📜 **Auto-Generated Scripts**: PowerShell scripts with complete restic commands
- 🔐 **User-Specific Encryption**: Password files can only be decrypted by the Windows user who created them
- ⏸️ **Pause After Completion**: Optional setting to keep window open after backup for review
- 🗑️ **Task Management**: View, create, update, and delete scheduled tasks from the app
- 🎯 **Smart Script Generation**: Includes all job settings (paths, tags, excludes, compression, etc.)
- 📂 **Organized Storage**: Scripts stored in `scheduled_tasks/` folder with job name
- ✅ **Multi-Repository Support**: For jobs with multiple repositories, schedules backup to the first one
- 🔔 **Toast Notifications**: PowerShell scripts show Windows toast notifications on completion (success/failure)

### Automated Retention Scheduling ✨ NEW
- 📅 **Task Scheduler Integration**: Create scheduled tasks to automatically clean up old snapshots
- 🪟 **Windows Task Scheduler**: One-click task creation with `schtasks.exe`
- 🐧 **Linux Cron**: Auto-generates cron job configuration for easy setup
- 🍎 **macOS LaunchAgent**: Provides ready-to-use launchd plist files
- ⏰ **Flexible Scheduling**: Choose Daily, Weekly, or Monthly retention runs
- 🕐 **Custom Time Selection**: Pick exact time (e.g., 2:00 AM for off-hours cleanup)
- 📆 **Day Selection**: Specify day of week (Weekly) or day of month (Monthly)
- ⚙️ **Independent Operation**: Scheduled tasks run even when app is closed
- 🗑️ **Task Management**: View, create, and delete scheduled tasks from the app
- 🔧 **Auto-Generated Scripts**: PowerShell scripts (Windows) with embedded restic commands
- ℹ️ **Best Practice Design**: Separates backup frequency from retention cleanup (run backups often, cleanup weekly)
- 🔔 **Toast Notifications**: PowerShell scripts show Windows toast notifications on completion (success/failure)

### Enhanced Snapshot Browsing ✨ NEW
- 🌳 **Hierarchical Tree View**: Browse snapshot contents in a natural folder structure (QTreeView)
- 📂 **Expandable Folders**: Navigate directory trees with expand/collapse controls
- 🔍 **Smart Tree Filtering**: Search auto-expands matching folders and shows parent hierarchy
- 📊 **Multi-Column Display**: View file names, types, sizes, dates, and permissions at a glance
- 🎨 **Color-Coded Items**: Folders in blue, sortable columns, alternating row colors
- ✅ **Multi-Select**: Select multiple files/folders to copy paths at once

### System Dependencies Management ✨ NEW
- 🔍 **Automatic Dependency Checking**: Check if Restic is installed with one click
- 📦 **One-Click Installation**: Install Restic directly from the Settings page
- 🪟 **Windows**: Uses `winget` (Windows Package Manager) for easy installation
- 🐧 **Linux**: Uses `apt` package manager with terminal guidance
- ✅ **Status Indicators**: Real-time status showing installed versions or missing packages
- 🔄 **Quick Verification**: Instantly verify installations after setup

### Application Password Protection ✨ NEW
- 🔒 **Startup Password**: Optional password protection for application access
- 🔐 **PBKDF2-HMAC-SHA256**: Industry-standard password hashing with 100,000 iterations
- 🧂 **Random Salt**: 32-byte cryptographically secure salt for each password
- 🪟 **Windows Registry Storage**: Hash stored in Registry (HKCU\Software\ResticManager) for enhanced security
- 📁 **Settings File Storage**: Non-Windows systems use encrypted settings file
- 🚫 **No Bypass**: Cannot be disabled by editing settings/JSON files
- 3️⃣ **Three Attempts**: Maximum 3 login attempts before application exit
- 🔄 **Change Password**: Requires current password verification
- ❌ **Remove Protection**: Authenticate to disable password requirement
- 🛡️ **Security**: One-way hash (password cannot be reversed), constant-time comparison
- ⚙️ **Easy Setup**: Configure in Settings > Security Settings

### File Restore & Browse Features ✨ NEW
- 📂 **Full Restore Functionality**: Restore files from any snapshot to any location
- 🗂️ **Browse Snapshot Contents**: View all files before restoring in a hierarchical tree view
- � **Browse Files**: Interactive snapshot browser using JSON API - no mounting required
- 📊 **Snapshot Selector**: Choose from all available snapshots with date/time/host information
- 🌳 **Hierarchical File Tree**: Browse repository contents in natural folder structure
- 📁 **File Details**: View file names, sizes, modification times, and types
- ✅ **Multi-Select Restore**: Select specific files/folders and restore them with one click
- ⚡ **Fast & Lightweight**: Uses `restic ls --json` for instant browsing (no FUSE/mount overhead)
- 🎯 **Path-Specific Restore**: Restore individual files/folders or entire snapshots
- 🚫 **No External Dependencies**: Works with standard restic installation - no WinFsp or FUSE required

### Performance & UX Improvements
- ⚡ **SQLite Dashboard Cache**: After the first Refresh, cards and charts restore from `restic_history.db` on startup (subtitle shows “Last refreshed: …”)
- 🔓 **Non-Modal Backup Progress**: Continue using the app while backups run in the background
- 🎚️ **Configurable Timeouts**: Set backup timeouts in hours (not seconds!) per job - no more 1-hour limit
- 📜 **Scrollable Backup Dialog**: All options neatly organized in a scrollable interface
- 📦 **Copy Snapshots Between Repos**: Fix backup mistakes by moving snapshots to the correct repository
- 📊 **Comprehensive Repository Stats**: Detailed breakdown showing Original Data Size, Repository Size, Total Saved (dedup+compression), and storage efficiency ratio - no more confusing stats!
- 🔔 **Windows Toast Notifications** ✨ NEW: Get notified when backups complete (success or failure)
  - Native Windows 10/11 toast notifications
  - Shows backup job name and repository
  - Success notifications with confirmation sound
  - Error notifications with alert sound (longer display)
  - Works for both GUI-initiated and scheduled backups
  - Scheduled tasks use built-in PowerShell notifications (no dependencies)
  - GUI backups use optional `winotify` package
  - Works even when app is minimized

### Dashboard Visual Charts
- 📊 **Interactive Charts**: Built-in QPainter charts (no extra chart package)
  - **Repository Storage Distribution**: Doughnut chart with centre total and side legend
  - **Snapshot Distribution**: Rounded gradient bars per repository
  - **Real-time Updates**: Charts refresh when clicking "Refresh Dashboard"
  - **Colour-Coded**: Deterministic per-repository colours shared with the jobs table
  - **Startup from cache**: Last refresh is restored from SQLite so charts are not blank after relaunch
  - **Empty State**: Clear prompt until the first successful refresh (or until cache exists)
  - **Recent Backup Jobs**: Duration + accurate last-run Status from the history database

### Advanced Repository Verification & Maintenance ✨ NEW
- 🔍 **Flexible Verification Levels**: Choose the right check for your needs
  - **Quick Check** (metadata only): Fast verification of repository structure - minutes
  - **Partial Data Check** (10% sample): Reads 10% of data packs to detect corruption - recommended for regular maintenance
  - **Full Data Check** (all data): Reads and verifies every byte - thorough but can take hours
- 🔧 **Rebuild Index**: One-click index reconstruction when needed
  - Safe operation that never deletes data
  - Rebuilds repository index from scratch
  - Automatically recommended when verification detects index issues
  - Useful after errors, crashes, or corruption
- 🎯 **Smart Detection**: Automatically detects when index rebuild is needed
  - Parsing restic output for index warnings
  - Offers to rebuild immediately when issues detected
  - Logs recommendations for future reference
- ⚡ **Optimized Timeouts**: Different timeouts for each verification level
  - Quick: 30 minutes, Partial: 1 hour, Full: 2 hours
  - Prevents premature timeout on large repositories

### Multi-Repository Backup Support ✨ NEW
- 🔄 **Backup to Multiple Repositories**: Select multiple target repositories for a single backup job
- 🛡️ **Redundancy & Safety**: Follow the 3-2-1 backup rule (3 copies, 2 different media, 1 offsite)
- 📦 **Sequential Execution**: Backs up to each repository one after another
- 📊 **Multi-Repo Progress**: Progress dialog shows "Repository X of Y" during execution
- 🔁 **Fault Tolerance**: If one repository fails, backup continues to the next
- ✅ **Flexible Selection**: Choose 1 or more repositories via multi-select list
- 📋 **Smart Display**: Job list shows "Repo1 +2 more" for jobs with multiple targets
- 🔙 **Backwards Compatible**: Seamlessly works with old single-repository jobs
- 💾 **Unified Configuration**: All repository backups use the same paths, tags, and options

### Enhanced Backup Options
- 🗜️ **Compression Control**: Choose off/auto/max compression per backup job
- 💾 **No Cache Option**: Disable local cache to save disk space
- 🔢 **Ignore Inode**: Handle inode changes for specific filesystems
- ⏱️ **Smart Timeout Management**: Customize timeout for each backup job based on data size
- 📦 **Pack Size Options**: Select from optimized pack sizes (16MB/32MB/64MB/128MB, default: 16MB)

## Current Implementation (v1.6.7)

### ✅ Completed Features

#### Core Infrastructure
- **Settings Manager**: JSON-based settings storage (restic_settings.json)
- **History Database**: SQLite store (`restic_history.db`) for job runs, repo stats samples, and dashboard cache (`core/history_db.py`)
- **License System**: Machine-bound license key activation (NEW v1.3.0)
  - Cross-platform machine ID generation (Windows, Linux, macOS)
  - HMAC-SHA256 cryptographic signatures prevent forgery
  - Machine-specific license binding (cannot share between computers)
  - Support for unlimited and time-limited licenses
  - License validation on startup
  - License management in Settings page
  - Separate license key generator tools (CLI and GUI)
- **Encrypted Password Storage**: Using `cryptography` library with Fernet encryption
  - PBKDF2HMAC with 100,000 iterations
  - Machine-specific encryption key (based on unique hardware/system ID)
  - Passwords securely stored in settings file
- **Application Password Protection**: Optional startup password to secure the application (NEW v1.3.0)
  - PBKDF2-HMAC-SHA256 password hashing with 100,000 iterations
  - 32-byte random salt per password (cryptographically secure)
  - Password hash stored in Windows Registry (HKCU\Software\ResticManager)
  - Settings file storage for non-Windows platforms
  - Three login attempts before application exit
  - Set/Change/Remove password from Settings page
  - Requires authentication before password removal
  - One-way cryptographic hash (password cannot be reversed)
  - Constant-time comparison prevents timing attacks
- **Theme Support**: 25 themes including:
  - light, dark, dark-cyan, dark-navy, dark-green, light-green
  - dark-purple, solarized-dark, light-blue, monokai-dark
  - dark-indigo, dark-magenta, sunset-orange, forest-moss, cool-grey
  - pure-black, midnight-blue, cyberpunk-neon, github-dark, vscode-dark
  - material-dark, dracula, nord-dark, amoled-black, matrix-green
- **Restic Command Wrapper**: Execute Restic CLI commands from Python
- **Worker Threads**: Non-blocking UI for long-running operations
- **Logging System**: Built-in activity logging

#### User Interface
- **Dynamic Splash Screen**: Displays 8 progress messages during app initialization
  - Loading settings
  - Initializing repositories
  - Checking snapshots
  - Loading backup jobs
  - Preparing dashboard
  - Verifying connections
  - Loading logs
  - Ready!

- **8 Main Pages**:
  1. **Dashboard** - Statistics, repository stats, and recent activity overview
     - **SQLite cache**: Cards/charts restore from last refresh on startup
     - **Manual Refresh**: "Refresh Dashboard" updates live stats and rewrites the cache
     - **Visual Charts**: Built-in doughnut + bar charts for repository storage and snapshots
       - Repository storage distribution (donut chart)
       - Snapshot counts per repository (bar chart)
       - Real-time updates with dashboard refresh
     - **Recent Backup Jobs**: Duration, Status (from last job run), Size, Last Backup, Schedule
  2. Repositories - Manage backup repositories
  3. Snapshots - Browse, view, restore, and manage snapshots
  4. Restore Files - Restore from backups
  5. **Backup Jobs** - Create, edit, manage, and run saved backup configurations
  6. Retention Policy - Set retention rules
  7. Logs - View application logs
  8. Settings - Configure application

- **Sidebar Navigation**: Clean menu system with Exit button
- **Responsive Layout**: Proper sizing and scroll areas

#### Repository Management ✅ FULLY IMPLEMENTED
- **Configured Repositories table**:
  - Name with coloured repository icon chip (same style as Dashboard → Recent Backup Jobs)
  - **Status**: Healthy / Warning / Unreachable / Unknown (from real connectivity checks)
  - Path, Type, Last Checked
  - **⋯ menu**: Check connection, Edit, Delete
- **Full Add/Edit Repository Dialog**:
  - Types: **Local folder**, **SFTP (NAS / remote)**, **HTTPS (REST server)**
  - Local: path with Browse
  - SFTP: host, port, username, remote path, absolute/relative, optional SSH key
  - HTTPS: URL + HTTP auth (anonymous / username+password / password only)
  - **Repo password** (encrypted at rest) with show/hide — encrypts backup data
  - **Initialize repository option** with real-time progress dialog
  - **Test connection button** — validates access with `restic snapshots --latest 1` and updates Status
  - Edit existing repositories; legacy cloud types still open if already saved
  - Delete repositories with confirmation
- **Windows UTF-8 Support**: Subprocess encoding fix for non-ASCII characters in Restic output

#### Snapshot Management ✅ FULLY IMPLEMENTED
- **Comprehensive Snapshot Details**: Display all metadata
  - Snapshot ID (short hash)
  - Date/Time of backup
  - Hostname
  - Username
  - Tags
  - Paths backed up
  - Excludes used
  - Statistics (files, directories, total size)
  - Parent snapshot ID
  - Restic version
- **Browse Content**: View files within a snapshot with hierarchical tree view ✨ ENHANCED
  - **Tree View Structure**: Files and folders displayed in hierarchical tree (QTreeView)
  - **Expandable/Collapsible Folders**: Navigate directory structure naturally
  - **Smart Columns**: Name, Type, Size, Modified Date, Permissions
  - Background loading with `restic ls --long`
  - **Tree Controls**:
    - Expand All / Collapse All buttons for quick navigation
    - Click folders to expand/collapse individual branches
    - Alternating row colors for better readability
    - Sortable columns (click headers to sort)
  - **Advanced Search & Filter**:
    - Real-time tree filtering (shows matching items and their parents)
    - Auto-expands matching folders when searching
    - Simple text search (matches folder and file names)
  - **Multi-Select Support**: Select multiple files/folders with Ctrl/Shift
  - **Copy Path(s)**: Copy full paths of selected items to clipboard
  - **Color-Coded**: Folders displayed in blue, files in default color
  - **Refresh Button**: Reload snapshot contents on demand
- **Diff Snapshots**: Compare changes between snapshots ✅ FULLY IMPLEMENTED
  - Executes `restic diff` command in background
  - Shows actual diff output (added, modified, removed files)
  - Statistics with color-coding (green/yellow/red)
  - Compares selected snapshot with previous (older) snapshot
  - Monospaced font for easy reading
  - Correct chronological comparison (oldest to newest)
- **Copy to Repository**: Move/copy snapshots between repositories ✅ NEW
  - Copy snapshots that were backed up to the wrong repository
  - Select destination repository from dropdown
  - **Configurable timeout** (0-24 hours, 0 = no limit)
  - Option to delete from source after successful copy (copy-then-delete operation)
  - **Real-time progress display** shows all output from restic
  - **Non-modal dialog** - access main GUI while copy runs
  - Uses `restic copy --repo2` command
  - Handles separate passwords for source and destination repos
  - Detailed error messages if copy fails
  - Perfect for correcting backup mistakes or consolidating backups
- **Forget/Delete**: Mark snapshots for deletion with confirmation
- **Prune Repository**: Remove unreferenced data to free disk space
- **Unlock Repository**: Clear stale locks with confirmation dialog
  - Handles repository locks from interrupted operations
  - Confirmation before unlocking

#### Restore Files ✅ FULLY IMPLEMENTED
- **Snapshot Selection**: Choose repository and snapshot to restore from
  - Automatic loading of snapshots with details (ID, date, hostname, paths)
  - Sorted by most recent first for easy access
- **Path-Based Restore**: Restore specific files/folders or entire snapshots
  - Leave path empty to restore all files
  - Specify a path to restore only that file/folder
- **Target Directory**: Select where to restore files
  - Browse button for easy directory selection
  - Files restored with original directory structure
- **Browse Snapshot Contents**: View all files in a snapshot before restoring
  - Displays complete file tree from `restic ls`
  - Copyable paths to paste into "Path to Restore" field
- **Browse Files** ✨ NEW FEATURE (replaces mount-based browsing):
  - **Interactive snapshot browser** - Browse ALL snapshots using restic's JSON API
  - **No mounting required** - Works without FUSE, WinFsp, or any external dependencies
  - **Snapshot dropdown**: Select from all available snapshots with full metadata
    - Shows: Date/Time | Hostname | Backup paths
    - Most recent snapshots first
  - **Hierarchical file tree**: Natural folder structure with expand/collapse
  - **File information display**:
    - File/folder names
    - Human-readable sizes (KB, MB, GB)
    - Modification timestamps
    - File type indicators (File/Folder)
  - **Multi-select restore**: Select specific files/folders and restore with one click
  - **Fast & efficient**: Uses `restic snapshots --json` and `restic ls --json`
    - No FUSE overhead
    - Direct JSON parsing for instant results
    - Much faster than traditional mount for large repositories
  - **Cross-platform**: Identical experience on Windows, Linux, and macOS
  - **Refresh capability**: Reload snapshot list or file tree on demand
  - **Built-in restore**: Select items → Choose target → Restore
  - **✅ Zero dependencies**: Only requires restic installation
- **Real-Time Restore Progress**:
  - Progress bar during restore operations
  - Detailed log output showing restored files
  - Success/failure notifications
  - Error details if restore fails
- **Restore Confirmation**: Confirms before starting restore to prevent accidents

#### Retention Policy & Automated Scheduling ✅ FULLY IMPLEMENTED
- **Retention Configuration**: Define snapshot retention rules
  - Keep Last: Keep the last N snapshots
  - Keep Hourly: Keep hourly snapshots
  - Keep Daily: Keep daily snapshots (default: 7)
  - Keep Weekly: Keep weekly snapshots (default: 4)
  - Keep Monthly: Keep monthly snapshots (default: 12)
  - Keep Yearly: Keep yearly snapshots
- **Manual Execution**: 
  - **Dry Run (Preview)**: See what would be deleted without making changes
  - **Apply Policy**: Execute retention policy with `restic forget --prune`
  - Real-time output showing deleted snapshots and space reclaimed
- **Automated Scheduling** ✨ NEW:
  - **Task Scheduler Integration**: Create system-level scheduled tasks
  - **Windows**: Creates Task Scheduler tasks using `schtasks.exe`
    - Generates PowerShell script with embedded restic command
    - Stores scripts in temp directory for persistence
    - Tasks run with highest privileges for repository access
  - **Linux**: Generates cron job configuration
    - Copy-to-clipboard functionality for easy setup
    - Standard crontab format
  - **macOS**: Provides launchd plist configuration
    - Ready-to-use LaunchAgent files
  - **Schedule Options**:
    - Frequency: Daily, Weekly, or Monthly
    - Time: Pick exact time (24-hour format, default: 2:00 AM)
    - Day of Week: Choose day for weekly runs (default: Sunday)
    - Day of Month: Select date (1-28) for monthly runs
  - **Task Management**:
    - **Create Scheduled Task**: One-click task creation
    - **View Tasks**: Opens Task Scheduler / cron editor
    - **Delete Task**: Remove scheduled retention tasks
  - **Task Naming**: Auto-generated names like `ResticRetention_RepositoryName`
  - **Independent Operation**: Tasks run even when application is closed
  - **Best Practice Design**: 
    - Run backups frequently (hourly/daily)
    - Run retention cleanup less often (weekly/monthly)
    - Reduces backup time and system load
    - Cleanup during off-hours (nights/weekends)

#### Backup Jobs System ✅ FULLY IMPLEMENTED
- **Persistent Job Storage**: Save backup configurations to settings.json
- **Create New Jobs**: Full job configuration dialog
  - Job name
  - **Multi-Repository Selection** ✨ NEW: Select one or more target repositories for redundancy
    - Multi-select list widget for choosing repositories
    - Helpful hint text: "Select one or more repositories to backup to (for redundancy)"
    - Visual indication of selected repositories
  - Multiple paths selection
  - Tags (comma-separated)
  - Exclude patterns (one per line)
  - Advanced options (see below)
- **Edit Existing Jobs**: Modify saved job configurations
  - Fully supports multi-repository jobs
  - Backwards compatible with old single-repository format
- **Delete Jobs**: Remove saved jobs with confirmation
- **Run Jobs**: Execute saved backup jobs with real-time progress
  - **Multi-Repository Execution** ✨ NEW: Sequential backup to all selected repositories
    - Progress dialog shows "Repository X of Y" during multi-repo backups
    - Continues to next repository even if one fails
    - All repositories use same backup paths, tags, excludes, and options
- **Non-Modal Progress Dialog**: Access main GUI while backups run
  - Dialog stays on top but doesn't block the main window
  - Start multiple operations while backup runs
  - Monitor progress without being locked in
- **Job List View**: Table showing all saved backup jobs with name, repository, paths, and tags
  - **Smart Repository Display** ✨ NEW: Shows single repo name or "Repo1 +2 more" for multiple

#### Real-Time Backup Progress ✅ FULLY IMPLEMENTED
- **Progress Dialog** during backup operations:
  - Progress bar with percentage
  - Files processed (done/total)
  - Bytes processed (done/total) with human-readable format
  - ETA (estimated time remaining)
  - Current files being processed (scrollable list)
  - **Dynamic output display**: All Restic JSON output shown in real-time
  - **Auto-scrolling**: Always shows the latest output
  - Completion indicator with visual separator
- **JSON Progress Parsing**: Parses Restic's JSON output from stderr
- **Non-Blocking Stream Reading**: Threaded queue-based output reading prevents UI freezing
- **Throttled Updates**: Maximum 10 updates/second to prevent UI freezing
- **UI Responsiveness**: QApplication.processEvents() for smooth progress updates
- **Cancel Button**: Stop backup in progress
  - Terminates background worker thread
  - Automatically unlocks repository if lock exists
  - Confirmation dialog when closing during active backup
- **Auto-Unlock After Completion**: Checks for locks and removes them automatically
  - Only unlocks if locks are actually present
  - Uses `restic list locks` to detect stale locks

#### Advanced Backup Options ✅ FULLY IMPLEMENTED
- **--exclude-caches**: Checkbox option (default: enabled)
- **--pack-size**: Pack size dropdown with options: 16MB, 32MB, 64MB, 128MB (default: 16MB)
- **--one-file-system**: Stay on same filesystem checkbox
- **--exclude-if-present**: Exclude directories with marker file (e.g., `.nobackup`)
- **Backup Timeout**: Configurable timeout in hours (0 = no timeout, default: 2 hours)
  - User-friendly hour-based input (no need to calculate seconds)
  - Prevents timeout on large backup jobs
  - Can be customized per backup job
- **--compression**: Compression level dropdown (off, auto, max)
  - `off`: No compression
  - `auto`: Automatic compression (default)
  - `max`: Maximum compression
- **--no-cache**: Disable local cache checkbox
  - Slower but uses less disk space
  - Useful for systems with limited storage
- **--ignore-inode**: Ignore inode number changes checkbox
  - Useful for certain filesystems or backup scenarios
- Standard exclude patterns support
- Tags support
- Multiple path selection
- **Scrollable Job Dialog**: All backup options in a scrollable interface
  - No more squished or cut-off options
  - Buttons always visible at bottom
  - Clean, organized layout

#### Backup Job Scheduling ✅ FULLY IMPLEMENTED
- **Schedule Configuration** in Backup Job Editor:
  - **Enable Scheduling**: Checkbox to enable/disable scheduled backups
  - **Frequency Options**: Daily, Weekly, or Monthly
  - **Time Selection**: Pick exact time for backup execution (e.g., 2:00 AM)
  - **Day Selection for Weekly**: Choose specific days (Mon-Sun) to run backups
  - **Run if Missed**: Auto-run at next logon if scheduled time was missed (optional)
  - **Pause After Completion**: Keep window open after backup finishes for result review (optional)
- **Windows Task Scheduler Integration**:
  - **One-Click Creation**: Creates scheduled task via `schtasks.exe` command
  - **Independent Execution**: Generated PowerShell scripts run restic directly
  - **History recording**: After restic exits, scripts call `restic_manager.py --record-job-run` so duration/success land in SQLite (brief Python invoke; backup itself still uses restic)
  - **Auto-Generated Scripts**: Complete backup command in PowerShell script format
  - **Script Storage**: Scripts saved in `scheduled_tasks/` folder with job name
  - **Secure Password Storage**: Uses Windows DPAPI to encrypt repository passwords
    - Password stored in separate `.password` file (encrypted)
    - Only the Windows user who created the task can decrypt it
    - PowerShell script loads and decrypts password at runtime
    - Password cleared from memory after backup completes
  - **Complete Configuration**: Scripts include all job settings:
    - Repository path and credentials
    - All backup paths
    - Tags, exclude patterns, compression settings
    - Pack size, cache options, and all other advanced settings
  - **Task Management**:
    - Create new scheduled tasks when job is saved
    - Update existing tasks when job configuration changes
    - Delete tasks when jobs are deleted
    - View task status in Windows Task Scheduler
- **Multi-Repository Note**: For jobs with multiple repositories, scheduled task backs up to the first repository only
- **Pause After Completion Feature**:
  - When enabled, PowerShell window stays open after backup
  - Shows "Press any key to continue..." prompt
  - Allows reviewing success/failure status and any warnings
  - Useful for testing and troubleshooting scheduled backups

#### Repository Statistics & Verification ✅ FULLY IMPLEMENTED
- **Comprehensive Dashboard Repository Stats**:
  - Repository selector dropdown
  - Refresh Stats button for on-demand updates
  - **Detailed statistics display**:
    - **Snapshots count**: Total number of snapshots
    - **Last backup**: Date/time of most recent backup
    - **Total files**: Number of files across all snapshots
    - **Storage Breakdown Section**:
      - **Original Data Size**: Total size before deduplication/compression
      - **Repository Size**: Actual storage used (after deduplication + compression)
      - **Total Saved**: Space saved with percentage (includes both deduplication AND compression)
      - **Storage efficiency ratio**: Shows compression factor (e.g., 0.25x = storing 25% of original)
    - **Last prune**: Days since last prune operation
    - **Corruption status**: Link to verify repository integrity
  - Multi-step background loading for accurate statistics
  - Clear breakdown prevents confusion between deduplication and compression
  - Uses `restic stats --mode raw-data` and `--mode restore-size` for accurate calculations
- **Verify Repository**:
  - Data verification button
  - Confirmation dialog before running check
  - Template ready for `restic check --read-data`

#### Settings & Configuration ✅ FULLY IMPLEMENTED
- **Application Settings**:
  - **Restic Path**: Configure path to Restic executable with browse button
  - **Theme Selection**: Choose from 25 different themes
  - **Auto Refresh Snapshots**: Toggle automatic snapshot refresh
  - **Refresh Interval**: Set refresh interval (10-3600 seconds)
  - Save button to persist all settings
- **System Dependencies** ✨ NEW:
  - **Restic Installation Check**:
    - Automatically detects if Restic is installed
    - Shows version information if found
    - One-click check to revalidate installation
    - **Install button** for missing Restic:
      - Windows: Uses `winget install restic`
      - Linux: Uses `sudo apt install restic`
      - Opens terminal with installation commands
  - **Cross-Platform Support**:
    - Windows: winget-based installations with admin prompts
    - Linux: apt-based installations with terminal and sudo
    - macOS: Manual installation guidance (Homebrew commands)
  - **Real-Time Status Updates**:
    - Green checkmark (✓) for installed software
    - Red X (✗) for missing software
    - Version information displayed
    - Auto-check on page load
- **License Management**:
  - View current license status with color coding
  - Display Machine ID with copy button
  - Update license key with activation dialog
  - Refresh license status
  - **Anti-Tampering Protection**:
    - Clock rollback detection prevents date manipulation
    - Cryptographic signature validation
    - Machine-specific binding
- **About Section**:
  - Application version display
  - Copyright information
  - Project description

### 🚧 To Be Implemented

#### High Priority

1. **Snapshot Loading & Display** (Partially Complete)
   - ✅ Snapshot details display implemented
   - ✅ Browse content with search/filter implemented
   - ✅ Diff snapshots fully implemented
   - Execute `restic snapshots --json` and populate table (UI ready)
   - Filtering and sorting in main snapshots view

2. **File Restore Operations** (UI Ready)
   - ✅ Browse snapshot file tree implemented (`restic ls --long`)
   - Select specific files/folders for restore
   - Execute restore with progress
   - Verify restored files

3. **Retention Policy Execution** (UI Ready)
   - Execute `restic forget` with policies
   - Preview what will be deleted (dry-run)
   - Execute `restic prune`
   - Show space savings

#### Medium Priority

5. **Backup Scheduling** ✅ IMPLEMENTED
   - ✅ Windows Task Scheduler integration (schtasks.exe)
   - ✅ Schedule management for backup jobs (Daily/Weekly/Monthly)
   - ✅ Automated backup execution (independent PowerShell scripts)
   - ✅ Secure password storage (Windows DPAPI encryption)
   - ✅ Pause after completion option for review
   - ✅ Create, update, and delete scheduled tasks from GUI
   - NOTE: **Backup scheduling is now implemented!** See Schedule section in Backup Job Editor
   - NOTE: **Retention scheduling also implemented!** See Retention Policy page for automated cleanup scheduling

6. **Enhanced Dashboard** ✅ MOSTLY COMPLETE
   - ✅ SQLite dashboard cache (startup paint without Refresh)
   - ✅ Manual refresh button for on-demand updates + repo_stats samples
   - ✅ Total repositories / snapshots / size / last backup
   - ✅ Recent Backup Jobs with Duration and accurate Status
   - Repository health status indicators (follow-up)
   - Trend charts over time (schema ready via `repo_stats` / `job_runs`)

#### Low Priority

7. **Advanced Features**
    - Repository migration/copying
    - Multi-repository operations
    - Backup statistics and charts
    - Email notifications
    - Export/import settings
    - Snapshot browsing and file-level restore

## Directory Structure

```
restic_manager.py              # Main application
restic_settings.json           # Settings / config (auto-created in the working directory)
restic_history.db              # Job history + dashboard cache (auto-created beside settings)
license.key                    # License key (created after activation)
scheduled_tasks/               # Generated Windows backup PowerShell scripts + DPAPI password files
core/                          # Non-UI helpers (SQLite history / job run recording)
ui/                            # App UI package (themes, title bar, dialogs, pages, charts, …)
tools/                         # Optional utilities (machine ID checker, license tests)
icons/                         # App / toolbar SVG + Windows/Linux app icons

# License System (admin — keep generators secure)
license_generator.py           # CLI license generator (KEEP SECURE!)
license_generator_gui.py       # GUI license generator (KEEP SECURE!)
license_generator_gui.spec     # PyInstaller spec for the license GUI

# Documentation
README.md                      # This file
DOCS/                          # License system docs
```

### Where data is stored

| Data | Location | Notes |
|------|----------|--------|
| App settings, repos, backup jobs | `restic_settings.json` (app working directory) | Created automatically on first save |
| Repo / HTTP passwords | Inside `restic_settings.json` | Fernet-encrypted with a **machine-derived** key (PBKDF2) — not portable to another PC as-is |
| Job runs, dashboard cache, repo stats | `restic_history.db` (beside settings) | SQLite; stdlib only |
| License | `license.key` | Machine-specific |
| Scheduled backup scripts | `scheduled_tasks/` | PowerShell + DPAPI-encrypted `.password` files (Windows) |
| Actual backup data | Your repo path / SFTP / REST URL | Managed by **restic**, not this app |

**Working directory:** when you start the app from this folder (or a PyInstaller build’s folder), settings resolve to that directory — e.g. `C:\python_scripts\restic_mngr\restic_settings.json`.

**Security Note:** The `license_generator.py` and `license_generator_gui.py` files should be kept secure and NOT distributed to end users. They are administrator/developer tools only.

## Dependencies

Already installed in your environment:
- PyQt6
- qdarkstyle
- cryptography (for password encryption and license system)

Optional (for Windows toast notifications):
- winotify (for backup completion notifications on Windows)

To install optional packages:
```powershell
.\env\Scripts\python.exe -m pip install winotify
```

Additional requirement:
- **Restic**: Download from https://restic.net/

To install cryptography:
```powershell
.\env\Scripts\python.exe -m pip install cryptography
```

## Running the Application

```powershell
# Activate your virtual environment
.\env\Scripts\Activate.ps1

# Run the application
python restic_manager.py
```

### Building a standalone executable (PyInstaller)

Use the project spec so icons and the `icons/` data folder are bundled correctly.
The command is the same on Windows and Linux:

```powershell
pyinstaller restic_manager.spec
```

Output: `dist/restic_manager` (or `dist/restic_manager.exe` on Windows).

**App icon files** (already in the repo):

| Platform | File | Used for |
|----------|------|----------|
| Windows | `icons/app.ico` | `.exe` icon + taskbar |
| Linux | `icons/app.png` | executable / desktop icon |
| Runtime (any) | `app.ico` → `app.png` → `app.svg` | window icon via `themes.app_window_icon()` |

The specs set **`upx=False`**. UPX compression often blanks or drops the Explorer
icon (especially after you rename the `.exe`), even though the icon is still
embedded. Rebuild with the spec after changing this.

If Explorer still shows a missing icon after a rename, that is usually the
Windows icon cache — reboot Explorer or rebuild the cache; the file itself is fine.

Do **not** build with a bare one-file command for the main app — it skips the
spec’s `datas` / `icon` settings:

```powershell
# Don't use for restic_manager:
pyinstaller --noconsole --onefile restic_manager.py
```

Alternate spec (keep in sync): `pyinstaller restic_manager_default.spec`

### CLI helpers (no GUI)

```powershell
# Run a backup job by name (cron / automation)
python restic_manager.py --run-job "My Job Name"

# Record a completed run into restic_history.db (used by Windows scheduled scripts)
python restic_manager.py --record-job-run "My Job Name" --repo-name "MyRepo" --duration 120 --success 1 --exit-code 0 --source scheduled
```

Job runs from the GUI, `--run-job`, and `--record-job-run` all write to the same history database.

## Configuration

On first run:
1. **Activate License**: Enter your license key when prompted
   - Copy your Machine ID using the Copy button
   - Send Machine ID to your license provider
   - Enter received license key and click "Activate License"
2. Install Restic if not already installed
3. Go to Settings and configure Restic path
4. Choose your preferred theme
5. Add your first repository

**License Management:**
- License keys are stored in `license.key` in the application directory
- Your license can be viewed and updated in Settings → License Information
- Each machine requires its own license (licenses are machine-specific)
- License validation occurs on application startup

## Quick Start Guide

### First Run - License Activation

On first run, the application requires a valid license key:

1. The **License Activation** dialog will appear automatically
2. Copy your **Machine ID** using the Copy button
3. Send your Machine ID to your license provider to request a license key
4. Paste the received license key into the text field
5. Click **Activate License**
6. Once activated, the application will start normally

**Note:** License keys are machine-specific and cannot be shared between computers. Each machine requires its own license.

### Adding Your First Repository

1. Click **Repositories** in the sidebar
2. Click **Add Repository**
3. Enter a **Name** (e.g. "NAS Backups")
4. Choose **Type**:
   - **Local folder** — path on disk; use **Browse**
   - **SFTP (NAS / remote)** — host, port, username, remote path; optional SSH key  
     (SSH key login must already work — see the in-dialog tip)
   - **HTTPS (REST server)** — URL such as `https://host:8000/repo/`  
     HTTP auth: Anonymous, Username + password, or Password only
5. Enter the **Repo password** (encrypts backup data; stored encrypted in settings)
6. Optionally check **Initialize repository now** for a brand-new repo
7. Optionally click **Test**, then **OK**

Config (including encrypted passwords) is saved to `restic_settings.json` in the app working directory.

**Repository Status:** In the Configured Repositories table, use **⋯ → Check connection** to refresh Status and Last Checked. Status values:
- **Healthy** — last check succeeded
- **Warning** — last success was more than 7 days ago
- **Unreachable** — last check failed
- **Unknown** — not checked yet

### Creating a Backup Job

1. Click **Backup Jobs** in the sidebar
2. Click **New Job** (or Edit an existing job)
3. In the dialog:
   - Enter a **Job Name** (e.g. "Daily Documents Backup")
   - Select one or more **repositories**
   - Click **Add Path** to add directories to backup
   - Optionally add tags and exclude patterns
   - Configure advanced options (exclude caches, pack size, timeout, compression, etc.)
4. Click **OK** to save

### Running a Backup Job

1. Click **Backup Jobs** in the sidebar
2. Select a saved job from the list
3. Click **Run Job**
4. A **non-modal** progress window appears (you can keep using the app):
   - Progress, files/bytes, ETA, live restic output
5. Click **Cancel** to stop (repository will auto-unlock)
6. Timeout follows the job setting (hours; `0` = no limit)

### Scheduling Automated Backups (Windows)

You can create scheduled tasks to run backup jobs automatically:

1. Click **Backup Jobs** in the sidebar
2. Select a backup job (or create a new one)
3. Click **Edit Job** or **Add Job**
4. In the **Schedule** section:
   - Check **Enable Scheduling**
   - Select **Frequency** (Daily, Weekly, Monthly)
   - Set the **Time** (e.g., 2:00 AM for nighttime backups)
   - For **Weekly**: Select which days to run (e.g., Mon, Wed, Fri)
   - For **Monthly**: Specify day of month (coming soon)
   - Optional: Check **Pause after completion** to review results
5. Click **OK** to save the job
6. The scheduled task is created automatically in Windows Task Scheduler
7. Verify in Task Scheduler: Look for "ResticBackup_YourJobName"

**Important Notes:**
- Scheduled tasks run independently - no need to keep the app open
- Repository passwords are securely encrypted using Windows DPAPI
- PowerShell scripts are generated in `scheduled_tasks/` folder
- Tasks run restic directly; after exit they briefly invoke Python `--record-job-run` to log duration/success into `restic_history.db`
- Multi-repository jobs: Only the first repository is backed up via schedule
- **Pause after completion**: Keeps window open to review success/failure

**To view or manage scheduled tasks:**
- Open Windows Task Scheduler
- Look under Task Scheduler Library
- Find tasks named "ResticBackup_*"
- You can manually run, disable, or view task history

### Managing Snapshots

1. Click **Snapshots** in the sidebar
2. Select a repository
3. Click **Refresh** to load snapshots
4. Select a snapshot to view details (ID, time, host, tags, paths, stats)
5. Use action buttons:
   - **Browse Content** - See files in snapshot with search/filter
     - Use & for AND search (term1 & term2)
     - Use | for OR search (term1 | term2)
     - Toggle Contains/Not Contains filter mode
   - **Diff with Previous** - See what changed
   - **Copy to Repository** - Move/copy snapshot to another repository
     - Useful if you backed up to the wrong repository
     - Choose destination repository
     - Option to delete from source (move mode)
   - **Forget (Delete)** - Mark for deletion
   - **Prune Repository** - Free disk space
   - **Unlock Repository** - Clear stale locks

### Copying Snapshots Between Repositories

If you accidentally backed up to the wrong repository:

1. Click **Snapshots** in the sidebar
2. Select the repository containing the misplaced snapshot
3. Select the snapshot you want to move/copy
4. Click **Copy to Repository** button
5. In the dialog:
   - Review snapshot details (ID, time, paths)
   - Select the **Destination Repository** from dropdown
   - **Set Timeout** (default: 6 hours, 0 = no limit for very large snapshots)
   - Check **Delete from source** if you want to move (copy-then-delete)
   - Click **OK**
6. **Progress window** shows real-time output (non-modal, you can use the app)
7. Wait for the copy to complete (may take hours for large snapshots)
8. If you chose delete option, confirm deletion after successful copy
9. The snapshot is now in the correct repository!

**Important Notes:**
- Set timeout to 0 for very large snapshots to avoid timeout errors
- The dialog is non-modal so you can continue using the app during copy
- Real-time output shows exactly what restic is doing
- The operation is copy-then-delete, not a true atomic move

### Viewing Repository Stats

1. Click **Dashboard** in the sidebar
2. **Fast Loading**: After at least one Refresh, cards/charts restore from `restic_history.db` on the next launch
3. Click **Refresh Dashboard** (title bar) to update live stats and rewrite the cache
4. **Recent Backup Jobs** shows Duration and last-run Status from the history DB
5. Under **Repository Statistics**, select a repository
6. Click **Refresh Stats** to see comprehensive repository information:
   - Snapshots count
   - Last backup date
   - Total files count
   - **Storage Breakdown**:
     - Original Data Size (before dedup/compression)
     - Repository Size (actual space used)
     - Total Saved (space saved by dedup + compression)
     - Storage efficiency ratio
   - Last prune date
   - Corruption status
5. Click **Verify Repository** to check data integrity
6. Use **Refresh Dashboard** button to update all statistics when needed

**Note**: 
- Stats loading may take a moment as it gathers comprehensive information from multiple restic commands.
- "Total Saved" includes BOTH deduplication and compression combined (restic doesn't separate them).
- Storage efficiency shows how efficiently your data is stored (lower is better, e.g., 0.25 = 4x compression).
2. Under **Repository Statistics**, select a repository
3. Click **Refresh Stats** to see repository information
4. Click **Verify Repository** to check data integrity

### Managing Your License

The Settings page includes license management features:

1. Click **Settings** in the sidebar
2. Scroll to the **License Information** section
3. View your current license status:
   - ✓ Green: License is valid (shows expiration date and days remaining)
   - ✗ Red: License expired or invalid
4. **Copy Machine ID**: Copy your unique machine identifier for license requests
5. **Update License Key**: Enter a new or replacement license key
6. **Refresh Status**: Revalidate your current license

**License Renewal/Update:**
- If your license expires, use "Update License Key" to enter a new key
- Your Machine ID never changes - use the same ID for renewals
- No need to restart the application after updating your license

## Implementation Guide

### License System (✅ Fully Implemented - v1.3.0)

The application includes a complete license key system that binds licenses to specific machines using hardware/system identifiers.

#### Machine ID Generation

```python
def get_machine_id():
    """Get cross-platform machine-specific identifier"""
    # Windows: Machine UUID from WMIC
    # Linux: /etc/machine-id or /var/lib/dbus/machine-id
    # macOS: Hardware UUID from IOPlatformExpertDevice
    # Fallback: MAC address + hostname + username
    
    machine_id = None
    system = platform.system()
    
    if system == "Windows":
        result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], ...)
        machine_id = result.stdout.lines[1].strip()
    elif system == "Linux":
        with open('/etc/machine-id', 'r') as f:
            machine_id = f.read().strip()
    # ... macOS and fallback implementations
    
    return machine_id
```

#### License Validation

```python
class LicenseManager:
    """Manage and validate machine-bound license keys"""
    
    _SECRET_KEY = b"your-secret-key-change-in-production"
    
    def validate_license(self) -> Tuple[bool, str]:
        """Validate the license key"""
        if not os.path.exists(self.license_file):
            return False, "No license key found"
        
        with open(self.license_file, 'r') as f:
            license_key = f.read().strip()
        
        # Decode: BASE64(machine_hash:expiry_date:signature)
        decoded = base64.b64decode(license_key).decode()
        machine_hash, expiry_str, signature = decoded.split(':')
        
        # Verify machine ID
        current_hash = hashlib.sha256(self.machine_id.encode()).hexdigest()[:16]
        if machine_hash != current_hash:
            return False, "License not valid for this machine"
        
        # Verify signature
        payload = f"{machine_hash}:{expiry_str}"
        expected_sig = hmac.new(_SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()[:32]
        if signature != expected_sig:
            return False, "Invalid license signature"
        
        # Check expiration
        if expiry_str != "unlimited":
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            if datetime.now() > expiry_date:
                return False, f"License expired on {expiry_str}"
        
        return True, "License is valid"
```

#### License Generation (For Administrators)

**Command Line Generator:**
```bash
# Generate unlimited license
python license_generator.py "MACHINE_ID_HERE"

# Generate 365-day license
python license_generator.py "MACHINE_ID_HERE" --days 365

# Save to file
python license_generator.py "MACHINE_ID_HERE" --days 365 --output license.key
```

**GUI Generator:**
```bash
# Launch graphical license generator
python license_generator_gui.py
```

**Generator Code:**
```python
def generate_license_key(machine_id: str, expiry_days: int = None) -> str:
    """Generate a license key for a specific machine"""
    machine_hash = hashlib.sha256(machine_id.encode()).hexdigest()[:16]
    
    if expiry_days is None:
        expiry_str = "unlimited"
    else:
        expiry_date = datetime.now() + timedelta(days=expiry_days)
        expiry_str = expiry_date.strftime("%Y-%m-%d")
    
    payload = f"{machine_hash}:{expiry_str}"
    signature = hmac.new(_SECRET_KEY, payload.encode(), hashlib.sha256).hexdigest()[:32]
    
    license_data = f"{machine_hash}:{expiry_str}:{signature}"
    return base64.b64encode(license_data.encode()).decode()
```

#### License Workflow

**Customer Side:**
1. Runs application → License Activation dialog appears
2. Copies Machine ID using Copy button
3. Sends Machine ID to administrator/vendor
4. Receives license key via email/support
5. Pastes license key into activation dialog
6. Clicks "Activate License"
7. License validated → Application starts

**Administrator Side:**
1. Receives Machine ID from customer
2. Runs license generator: `python license_generator.py "MACHINE_ID" --days 365`
3. Sends generated license key to customer
4. Customer activates and application works

#### Security Features

- **Machine-Bound**: License keys contain machine ID hash - cannot be shared
- **Cryptographically Signed**: HMAC-SHA256 prevents forgery/tampering
- **Expiration Support**: Time-limited trials or subscriptions
- **Secure Storage**: License stored in `license.key` file
- **No Cloud Required**: All validation is local

#### Available Tools

1. **license_generator.py** - CLI tool for generating licenses (KEEP SECURE!)
2. **license_generator_gui.py** - GUI tool for license generation
3. **tools/check_machine_id.py** - Utility for customers to get their Machine ID
4. **tools/test_license.py** - Test license generation/validation
5. **LICENSE_SYSTEM.md** - Complete documentation
6. **LICENSE_QUICKSTART.md** - Quick start guide

**Important:** Keep the license generator tools secure! Do not distribute to end users.

### Using Encrypted Passwords

Passwords are automatically encrypted when repositories are added:

```python
# Getting repository with decrypted password
def get_repository_by_name(self, repo_name):
    repositories = self.settings_manager.get("repositories")
    repo = next((r for r in repositories if r["name"] == repo_name), None)
    if repo and repo.get("password"):
        # Decrypt password for use
        password = self.settings_manager.password_manager.decrypt(repo["password"])
        return repo, password
    return repo, ""

# Using password with Restic command
env = {"RESTIC_PASSWORD": password}
args = ["-r", repo["path"], "snapshots", "--json"]
success, stdout, stderr = self.restic_cmd.run(args, env)
```

### Application Password Protection (✅ Fully Implemented)

Protect your application with an optional startup password. When enabled, users must authenticate before accessing the application.

#### Features

- **PBKDF2-HMAC-SHA256 Hashing**: Industry-standard password hashing with 100,000 iterations
- **Random Salt**: 32-byte cryptographically secure random salt per password
- **Secure Storage**:
  - **Windows**: Password hash stored in Windows Registry (`HKCU\Software\ResticManager`)
  - **Linux/macOS**: Password hash stored in settings file
- **Three Attempts**: Maximum 3 login attempts before application exits
- **One-Way Hash**: Password cannot be reversed from stored hash
- **Timing Attack Protection**: Constant-time comparison prevents timing-based attacks

#### Setting Up Password Protection

1. Navigate to **Settings** page
2. Find the **Security Settings** section
3. Click **Set Password**
4. Enter your desired password (minimum 4 characters)
5. Confirm the password
6. Password is immediately active

**Storage Location:**
- Windows: `HKCU\Software\ResticManager\AppPasswordHash` and `AppPasswordSalt`
- Other platforms: `restic_settings.json` (encrypted hash and salt)

#### Changing Your Password

1. Navigate to **Settings** > **Security Settings**
2. Click **Change Password**
3. Enter your current password for verification
4. Enter and confirm your new password
5. Password is updated immediately

#### Removing Password Protection

1. Navigate to **Settings** > **Security Settings**
2. Click **Remove Password**
3. Enter your current password for authentication
4. Confirm the removal
5. Password protection is disabled

#### Security Notes

- **Windows Registry Storage**: On Windows, the password hash is stored in the Registry, which requires Windows API knowledge to access (more secure than JSON file editing)
- **No Bypass**: The application checks for password hash presence at startup - cannot be bypassed by editing settings
- **Desktop App Limitations**: Like all desktop applications, password protection provides a convenience barrier but cannot prevent access from users with full filesystem/Registry access
- **Combine with OS Security**: For maximum security, combine with Windows user accounts, disk encryption, or OS-level security features

#### Password Requirements

- Minimum length: 4 characters
- No maximum length
- All characters supported (letters, numbers, symbols)
- Case-sensitive

### Repository Management (✅ Fully Implemented)
The repository dialog is fully functional with initialization and testing

### Real-Time Backup Progress (✅ Fully Implemented)
Parse JSON progress from Restic and display

### Browse Snapshot Content (✅ Fully Implemented)

### Lock Management (✅ Fully Implemented)

### Creating Backups (✅ Fully Implemented)

### Applying Retention (✅ Fully Implemented)

#### Prune Repository
```python
def prune_repository(self):
    # restic -r <repo> prune
    args = ["-r", repo["path"], "prune"]
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
```

#### Browse Snapshot Content

#### Diff Snapshots (✅ Fully Implemented)

#### Repository Statistics

## Key Design Decisions

1. **Settings Storage**: Simple JSON file for configuration only
   - Added `backup_jobs` array for persistent job storage
   - Each job stores full configuration (paths, tags, excludes, advanced options)
   - **History / time-series** (durations, failures, dashboard samples) live in SQLite `restic_history.db` via `core/history_db.py`

2. **Password Security**: Fernet encryption with PBKDF2HMAC key derivation
   - Machine-specific encryption (prevents password portability across machines)
   - 100,000 PBKDF2 iterations for strong key derivation

3. **Theme System**: Reused your exact theme implementation (25 themes)

4. **Command Execution**: Wrapper class for consistent Restic interaction
   - Subprocess with UTF-8 encoding and error handling for Windows
   - Environment variable RESTIC_PASSWORD for secure password passing

5. **Threading**: Worker threads prevent UI freezing
   - QThread-based ResticWorker for background operations
   - pyqtSignal for progress updates
   - Proper thread cleanup and cancellation support

6. **Modular Pages**: Each feature is a separate page in stacked widget
   - "Backup Jobs" page for managing saved configurations
   - Dashboard, Repositories, Snapshots, Restore, Retention, Logs, Settings

7. **Progress Tracking**: Real-time JSON parsing from Restic
   - Parse stderr (not stdout) for JSON progress data
   - Throttled updates (10/second max) to prevent UI overload
   - QApplication.processEvents() for responsive UI during updates
   - ETA calculation based on elapsed time and percentage

8. **Lock Management**: Comprehensive repository lock handling
   - Manual unlock with confirmation
   - Automatic unlock on backup cancellation
   - Auto-cleanup after completion (only if locks detected)
   - Prevents stale locks from interrupted operations

9. **Search & Filter**: Flexible file searching in snapshots
   - AND operator (&) - all terms must match
   - OR operator (|) - any term can match
   - Contains / Not Contains modes
   - Real-time filtering without re-loading data

10. **Background Loading**: Long operations in separate threads
    - Repository initialization with progress dialog
    - Snapshot content browsing (restic ls --long)
    - Backup execution with real-time progress
    - Non-blocking UI for all operations

## Next Steps

1. ✅ ~~**Repository Management**~~ - COMPLETED
2. ✅ ~~**Backup Jobs System**~~ - COMPLETED
3. ✅ ~~**Real-Time Progress Tracking**~~ - COMPLETED
4. ✅ ~~**Snapshot Details & Browse Content**~~ - COMPLETED
5. ✅ ~~**Lock Management**~~ - COMPLETED
6. ✅ ~~**Diff Snapshots**~~ - COMPLETED
7. ✅ ~~**Add Scheduling**~~ - COMPLETED (Windows Task Scheduler automation for backup jobs)
8. **Implement Snapshot Table Loading**: Execute and parse `restic snapshots --json`
9. **Complete Restore Operations**: Implement file selection and restore execution
10. **Connect Forget/Prune**: Wire up snapshot deletion and repository pruning

## Estimated Implementation Time

- ✅ Repository Management: ~~4-6 hours~~ COMPLETED
- ✅ Password Encryption: ~~2-3 hours~~ COMPLETED  
- ✅ Advanced Backup Options: ~~2-3 hours~~ COMPLETED
- ✅ Snapshot Action Buttons: ~~3-4 hours~~ COMPLETED
- ✅ Repository Initialize/Test: ~~2-3 hours~~ COMPLETED
- ✅ Backup Jobs System: ~~6-8 hours~~ COMPLETED
- ✅ Real-Time Progress Tracking: ~~4-5 hours~~ COMPLETED
- ✅ Snapshot Details Display: ~~2-3 hours~~ COMPLETED
- ✅ Browse Snapshot Content: ~~4-5 hours~~ COMPLETED
- ✅ Search & Filter: ~~2-3 hours~~ COMPLETED
- ✅ Lock Management: ~~3-4 hours~~ COMPLETED
- ✅ Progress UI Optimization: ~~2-3 hours~~ COMPLETED
- ✅ Diff Implementation: ~~2-3 hours~~ COMPLETED
- ✅ Dynamic Output Display: ~~1-2 hours~~ COMPLETED
- Snapshot Loading (main table): 2-3 hours
- Restore Operations: 6-8 hours
- Forget/Prune Execution: 2-3 hours
- Repository Stats/Verify: 2-3 hours
- Scheduling: 8-10 hours

**Completed: ~48-60 hours**
**Remaining: ~20-27 hours for full implementation**

## Notes

- ✅ All UI elements are in place and functional
- ✅ Theme system works perfectly (25 themes total)
- ✅ Settings persistence is implemented
- ✅ Password encryption is working (tested and secure)
- ✅ Repository dialog fully functional (add/edit/delete/initialize/test)
- ✅ Advanced backup options implemented and saved in jobs
- ✅ Snapshot details display complete with all metadata
- ✅ Browse content fully working with background loading
- ✅ Diff snapshots fully implemented with statistics
- ✅ Dynamic output display with auto-scrolling
- ✅ Non-blocking stream reading for progress updates
- ✅ Search & filter with AND/OR operators implemented
- ✅ Backup Jobs system fully operational with persistent storage
- ✅ Real-time backup progress with JSON parsing, ETA, throttling
- ✅ Comprehensive lock management (unlock, cancel, auto-cleanup)
- ✅ UTF-8 encoding fix for Windows subprocess
- ✅ Progress UI optimization to prevent freezing
- ✅ Exit menu item functional
- Snapshot table loading (execute restic snapshots --json) still needed
- Restore operations need implementation
- Error handling framework is ready
- Worker threads prevent UI freezing

## Recent Updates (Latest)

### Version 1.3.0 - March 13, 2026

**Major New Features:**
- ✅ **License System - Fully Implemented**: Complete machine-bound licensing
  - Cross-platform machine ID generation (Windows/Linux/macOS with fallback)
  - HMAC-SHA256 cryptographic signature verification
  - License validation on application startup
  - License activation dialog for first-run and invalid licenses
  - License management in Settings page:
    - View license status (valid/expired/invalid)
    - Copy Machine ID for license requests
    - Update/renew license key without restart
    - Refresh license status
  - Support for unlimited and time-limited licenses
  - License generator tools (CLI and GUI)
  - Comprehensive documentation (LICENSE_SYSTEM.md, LICENSE_QUICKSTART.md)
  - Utility scripts (`tools/check_machine_id.py`, `tools/test_license.py`)
  - Machine-specific binding prevents license sharing

**New Features:**
- ✅ **Diff Snapshots - Fully Implemented**: Compare changes between snapshots
  - Executes `restic diff` command in background worker thread
  - Shows actual diff output (added, modified, removed files)
  - Statistics with color-coding (green for added, yellow for modified, red for removed)
  - Monospaced font for easy reading
  - Compares selected snapshot with previous (older) snapshot
  - Fixed chronological comparison logic (oldest first = row 0)
- ✅ **Dynamic Output Display**: Real-time backup output in progress dialog
  - All Restic JSON output displayed as it arrives
  - Auto-scrolling to always show latest output
  - Throttled scrolling (20 updates/second) to prevent UI lag
  - Visual completion separator at end of backup

**Bug Fixes:**
- Fixed snapshot comparison logic - now correctly identifies oldest snapshot
- Fixed progress dialog hanging after backup completion
- Implemented non-blocking stream reading with threaded queues
- Fixed JSON progress lines not appearing in output display

**Technical Improvements:**
- Non-blocking stdout/stderr reading using Queue and threading
- Proper process completion detection
- Summary message triggers 100% progress update
- All output lines emitted to progress signal for display

### Version 1.2.0 - March 13, 2026

**Major Features Added:**
- ✅ **Dynamic Splash Screen**: Shows 8 progress messages during app initialization
- ✅ **Backup Jobs System**: Save, edit, delete, and run backup configurations
  - Persistent storage in settings.json
  - Full job management UI (create/edit/delete/run)
  - Rename from "Create Backup" to "Backup Jobs" page
- ✅ **Real-Time Backup Progress**: Complete progress tracking during backups
  - JSON progress parsing from Restic stderr output
  - Progress bar with percentage
  - Files and bytes processed (done/total)
  - ETA calculation and display
  - Current files being processed (scrollable list)
  - Throttled updates (max 10/second) to prevent UI freezing
  - QApplication.processEvents() for responsive UI
- ✅ **Comprehensive Lock Management**:
  - Unlock Repository button with confirmation
  - Cancel backup button with automatic unlock
  - Close warning dialog during active backups
  - Auto-unlock after backup completion (only if locks exist)
- ✅ **Complete Snapshot Details**: Display all metadata
  - Snapshot ID, date/time, host, username
  - Tags, paths, excludes
  - Statistics (files, directories, size)
  - Parent snapshot, Restic version
- ✅ **Browse Snapshot Content**: Fully functional file browsing
  - Background loading with `restic ls --long`
  - File path, permissions, size, modification date
  - Advanced search with AND (&) / OR (|) operators
  - Contains / Not Contains filter modes
  - Real-time filtering
- ✅ **Repository Operations**:
  - Initialize repository with real-time progress dialog
  - Test connection functionality
  - UTF-8 encoding fix for Windows subprocess (handles non-ASCII characters)
- ✅ **Exit Menu Item**: Properly exits application with QApplication.quit()

**Technical Improvements:**
- Windows UTF-8 subprocess support (encoding='utf-8', errors='replace')
- JSON progress parsing from stderr (Restic outputs to stderr, not stdout)
- Progress throttling to prevent UI freezing
- Background worker threads for all long-running operations
- Automatic lock detection and cleanup
- Improved error handling and user feedback

**Settings Schema Updates:**
- Added `backup_jobs` array to settings.json
- Job structure: name, repository, paths, tags, excludes, advanced options

### Version 1.0.0 - Initial Release

**Added:**
- ✅ Encrypted password storage with cryptography library
- ✅ Full repository add/edit dialog with password support
- ✅ Advanced backup options (--exclude-caches, --pack-size, --one-file-system, --exclude-if-present)
- ✅ Snapshot management buttons (Browse Content, Diff, Forget, Prune)
- ✅ Repository statistics section on Dashboard
- ✅ Repository verification button
- ✅ All 25 themes fully working (including vscode-dark, github-dark, material-dark, dracula, nord-dark)
- ✅ Password show/hide toggle in repository dialog
- ✅ Machine-specific encryption key for password security

**Technical Details:**
- Password encryption using Fernet with PBKDF2HMAC (100,000 iterations)
- Passwords stored encrypted in restic_settings.json
- All dialogs and UI elements ready for command execution

## License Key Generation (For Administrators)

The application includes tools for generating license keys. These should only be used by administrators/vendors.

### Command-Line Generator

```bash
# Generate unlimited license
python license_generator.py "CUSTOMER_MACHINE_ID"

# Generate 30-day trial
python license_generator.py "CUSTOMER_MACHINE_ID" --days 30

# Generate 1-year license
python license_generator.py "CUSTOMER_MACHINE_ID" --days 365

# Save directly to file
python license_generator.py "CUSTOMER_MACHINE_ID" --days 365 --output customer_license.key
```

### GUI Generator

For non-technical staff, use the graphical generator:

```bash
python license_generator_gui.py
```

Features:
- Paste customer's Machine ID
- Select license type (unlimited or time-limited)
- Set duration for time-limited licenses
- Generate with one click
- Copy to clipboard or save to file

### Customer Support Workflow

1. **Customer Reports Issue**: "I need a license key"
2. **Request Machine ID**: Ask customer to run `python tools/check_machine_id.py` or copy from activation dialog
3. **Generate License**: Use license generator with their Machine ID
4. **Send to Customer**: Email or provide through support portal
5. **Customer Activates**: Paste into activation dialog
6. **Verification**: Customer confirms application starts successfully

### Important Security Notes

- **Keep generators secure**: Do not distribute `license_generator.py` or `license_generator_gui.py`
- **Change secret key**: Before production, change `_SECRET_KEY` in both files to match
- **Secret key must match**: The key in `restic_manager.py` and generators must be identical
- **Machine IDs are not secret**: They identify machines but are not sensitive
- **One license per machine**: Licenses cannot be shared between computers

### Checking Machine ID

Customers can check their own Machine ID:

```bash
python tools/check_machine_id.py
```

This displays:
- Detected operating system
- Machine ID detection method used
- The unique Machine ID
- Auto-copies to clipboard (if pyperclip installed)

## Support

The application logs errors to the Logs page. Check there first if something doesn't work.

For license-related issues:
- **"No license key found"**: Normal on first run - enter license in activation dialog
- **"License not valid for this machine"**: License was generated for different machine ID
- **"License expired"**: Request new license or renewal from administrator
- **"Invalid license signature"**: License may be corrupted or secret keys don't match

For license requests or renewals, provide your Machine ID (found in Settings → License Information).

---

## License System Summary

### Key Features
✅ **Machine-bound licensing** - Licenses tied to unique hardware/system IDs  
✅ **Cryptographically secure** - HMAC-SHA256 prevents forgery  
✅ **Cross-platform** - Works on Windows, Linux, macOS  
✅ **Time-limited trials** - Support for expiring licenses  
✅ **Easy activation** - Simple dialog-based activation  
✅ **In-app management** - Update license without restart  
✅ **Admin tools** - CLI and GUI license generators  

### Quick Reference

**For Users:**
- First run → License Activation dialog
- Copy Machine ID → Send to administrator
- Receive license key → Paste and activate
- Manage in Settings → License Information

**For Administrators:**
- Receive Machine ID from user
- Generate: `python license_generator.py "MACHINE_ID" --days 365`
- Send license key to user
- Done!

**Files:**
- `license.key` - Activated license (don't delete!)
- `license_generator.py` - CLI generator (keep secure!)
- `license_generator_gui.py` - GUI generator (keep secure!)
- `tools/check_machine_id.py` - Machine ID checker
- `LICENSE_SYSTEM.md` - Full documentation
- `LICENSE_QUICKSTART.md` - Quick start guide

**Security:**
- Change `_SECRET_KEY` before production
- Keep generators secure (don't distribute)
- Licenses cannot be shared between machines
- Machine IDs are not sensitive (safe to share for licensing)

---

**Version:** 1.3.0  
**License System:** Fully Implemented  
**Last Updated:** March 13, 2026
