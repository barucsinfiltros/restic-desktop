# Restic Backup Manager

A PyQt6 GUI application for managing Restic backups with a familiar interface similar to your Network Management Tool.

## What's New in Recent Updates

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
- ⚡ **Smart Dashboard Caching**: Dashboard loads instantly after first view - no more waiting when switching menus!
- 🔓 **Non-Modal Backup Progress**: Continue using the app while backups run in the background
- 🎚️ **Configurable Timeouts**: Set backup timeouts in hours (not seconds!) per job - no more 1-hour limit
- 📜 **Scrollable Backup Dialog**: All options neatly organized in a scrollable interface
- 📦 **Copy Snapshots Between Repos**: Fix backup mistakes by moving snapshots to the correct repository
- 📊 **Comprehensive Repository Stats**: Detailed breakdown showing Original Data Size, Repository Size, Total Saved (dedup+compression), and storage efficiency ratio - no more confusing stats!

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

## Current Implementation (v1.3.0)

### ✅ Completed Features

#### Core Infrastructure
- **Settings Manager**: JSON-based settings storage (restic_settings.json)
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
     - **Smart Caching**: Dashboard loads instantly after first view
     - **Manual Refresh**: "Refresh Dashboard" button to update stats on demand
     - No delays when switching between menus
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
- **Full Add/Edit Repository Dialog**:
  - Support for local, SFTP, S3, B2, Azure, GS, REST repositories
  - Repository name and type selection
  - Path/URL input with browse button for local paths
  - **Encrypted password field** with show/hide toggle
  - **Initialize repository option** with real-time progress dialog
  - **Test connection button** - validates repository access with `restic snapshots --latest 1`
  - Edit existing repositories
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

5. **Backup Scheduling**
   - Windows Task Scheduler integration
   - Cron-like scheduler UI
   - Schedule management for backup jobs
   - Automated backup execution
   - NOTE: **Retention scheduling is now implemented!** See Retention Policy page for automated cleanup scheduling

6. **Enhanced Dashboard** (Partially Complete)
   - ✅ Smart caching for instant loading
   - ✅ Manual refresh button for on-demand updates
   - Calculate total repositories
   - Count total snapshots across all repos
   - Calculate total backup size
   - Show last backup time
   - Repository health status indicators

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
restic_settings.json           # Settings (auto-created)
license.key                    # License key (created after activation)

# License System (v1.3.0)
license_generator.py           # CLI license generator (KEEP SECURE!)
license_generator_gui.py       # GUI license generator (KEEP SECURE!)
check_machine_id.py            # Machine ID checker utility
test_license.py                # License testing script
LICENSE_SYSTEM.md              # Complete license documentation
LICENSE_QUICKSTART.md          # Quick start for license system

# Documentation
RESTIC_MANAGER_README.md       # This file
```

**Security Note:** The `license_generator.py` and `license_generator_gui.py` files should be kept secure and NOT distributed to end users. They are administrator/developer tools only.

## Dependencies

Already installed in your environment:
- PyQt6
- qdarkstyle
- cryptography (for password encryption and license system)

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
2. Click **Add Repository** button
3. In the dialog:
   - Enter a **Name** (e.g., "My Backup")
   - Select **Type** (local, sftp, s3, etc.)
   - Enter **Path/URL** (use Browse for local paths)
   - Enter **Password** (will be encrypted automatically)
   - Check **Show password** if you want to verify it
   - Optionally check **Initialize repository now** for new repos
4. Click **OK**
scrollable dialog:
   - Enter a **Job Name** (e.g., "Daily Documents Backup")
   - Select your repository from the dropdown
   - Click **Add Path** to add directories to backup
   - Optionally add tags (comma-separated)
   - Add exclude patterns (one per line)
   - Configure **Advanced Options**:
     - ✅ Exclude Caches (recommended)
     - **Pack Size** (16MB/32MB/64MB/128MB, default: 16MB)
     - One File System (stay on same drive)
     - **Backup Timeout** (in hours, 0 = no timeout)
     - Exclude If Present (marker file like .nobackup)
     - **Compression** (off/auto/max)
     - **No Cache** (use less disk space)
     - **Ignore Inode** (for certain filesystems)
4. Scroll through all options (dialog is fully scrollable)
5  - Optionally add tags (comma-separated)
   - Add exclude patterns (one per line)
   - Configure **Advanced Options**:
     - ✅ Exclude Caches (recommended)
     - Set Pack Size if needed (0 = default)
   **Non-modal progress window** appears (main GUI remains accessible):
   - Progress bar with percentage
   - Files and bytes processed
   - ETA (estimated time remaining)
   - Current files being backed up
   - Real-time output from Restic
5. **Continue working**: Navigate to other pages, check snapshots, etc.
6. Click **Cancel** to stop the backup (repository will auto-unlock)
7. Backup respects your configured timeout (no more 1-hour hardcoded limit!
1. Click **Backup Jobs** in the sidebar
2. Select a saved job from the list
3. Click **Run Job** button
4. Watch real-time progress:
   - Progress bar with percentage
   - Files and bytes processed
   - ETA (estimated time remaining)
   - Current files being backed up
5. Click **Cancel** to stop the backup (repository will auto-unlock)

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
2. **Fast Loading**: Dashboard shows cached data instantly
3. Under **Repository Statistics**, select a repository
4. Click **Refresh Stats** to see comprehensive repository information:
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
3. **check_machine_id.py** - Utility for customers to get their Machine ID
4. **test_license.py** - Test license generation/validation
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

### Repository Management (✅ Fully Implemented)

The repository dialog is fully functional with initialization and testing:

```python
def add_repository(self):
    dialog = RepositoryDialog(self, self.settings_manager)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        repo_data = dialog.get_repository_data()
        # Password is automatically encrypted in get_repository_data()
        
        # Initialize if requested
        if dialog.initialize_checkbox.isChecked():
            self.initialize_repository(repo_data)
        
        # Save repository
        repositories = self.settings_manager.get("repositories")
        repositories.append(repo_data)
        self.settings_manager.save_settings()

def test_connection(self, repo_data, password):
    """Test repository connection"""
    args = ["-r", repo_data["path"], "snapshots", "--latest", "1"]
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
    return success
```

### Backup Jobs System (✅ Fully Implemented)

Save and manage backup configurations:

```python
def save_backup_job(self):
    """Save current backup configuration as a job"""
    job_data = {
        "name": self.job_name_input.text(),
        "repository": self.backup_repo_combo.currentText(),
        "paths": [self.backup_paths_list.item(i).text() 
                 for i in range(self.backup_paths_list.count())],
        "tags": [tag.strip() for tag in self.backup_tags_input.text().split(",") 
                if tag.strip()],
        "excludes": [p.strip() for p in 
                    self.backup_exclude_input.toPlainText().split("\n") 
                    if p.strip()],
        "exclude_caches": self.exclude_caches_check.isChecked(),
        "pack_size": self.pack_size_spin.value(),
        "one_file_system": self.one_file_system_check.isChecked(),
        "exclude_if_present": self.exclude_if_present_input.text().strip()
    }
    
    # Save to settings
    backup_jobs = self.settings_manager.get("backup_jobs", [])
    backup_jobs.append(job_data)
    self.settings_manager.set("backup_jobs", backup_jobs)
    self.settings_manager.save_settings()

def run_backup_job(self, job_data):
    """Execute a saved backup job with real-time progress"""
    # Get repository and decrypt password
    repo, password = self.get_repository_by_name(job_data["repository"])
    
    # Build command
    args = ["-r", repo["path"], "backup", "--json"]
    args.extend(job_data["paths"])
    
    for tag in job_data.get("tags", []):
        args += ["--tag", tag]
    
    for pattern in job_data.get("excludes", []):
        args += ["--exclude", pattern]
    
    if job_data.get("exclude_caches", True):
        args.append("--exclude-caches")
    
    # ... add other options
    
    # Execute with progress tracking
    env = {"RESTIC_PASSWORD": password}
    worker = ResticWorker(self.restic_cmd, args, env)
    worker.progress_data.connect(self.update_backup_progress)
    worker.start()
```

### Real-Time Backup Progress (✅ Fully Implemented)

Parse JSON progress from Restic and display:

```python
def _parse_progress(self, line):
    """Parse JSON progress output from Restic"""
    try:
        data = json.loads(line)
        if data.get("message_type") == "status":
            percent = data.get("percent_done", 0) * 100
            files_done = data.get("files_done", 0)
            files_total = data.get("total_files", 0)
            bytes_done = data.get("bytes_done", 0)
            bytes_total = data.get("total_bytes", 0)
            
            # Calculate ETA
            if percent > 0:
                elapsed = time.time() - self.start_time
                eta_seconds = (elapsed / (percent / 100)) - elapsed
                eta = self.format_eta(eta_seconds)
            else:
                eta = "Calculating..."
            
            # Emit progress signal
            self.progress_data.emit({
                "percent": percent,
                "files_done": files_done,
                "files_total": files_total,
                "bytes_done": bytes_done,
                "bytes_total": bytes_total,
                "eta": eta,
                "current_files": data.get("current_files", [])
            })
    except json.JSONDecodeError:
        pass

def update_backup_progress(self, progress_dict):
    """Update progress dialog (throttled to 10 updates/second)"""
    current_time = time.time()
    if current_time - self.last_update_time < 0.1:  # 100ms throttle
        return
    
    self.last_update_time = current_time
    
    # Update UI
    self.progress_bar.setValue(int(progress_dict["percent"]))
    self.files_label.setText(f"{progress_dict['files_done']}/{progress_dict['files_total']}")
    self.bytes_label.setText(f"{self.format_bytes(progress_dict['bytes_done'])}/
                                {self.format_bytes(progress_dict['bytes_total'])}")
    self.eta_label.setText(progress_dict["eta"])
    
    # Update current files list
    for file in progress_dict.get("current_files", []):
        self.current_files_list.addItem(file)
    
    # Process UI events to keep responsive
    QApplication.processEvents()
```

### Browse Snapshot Content (✅ Fully Implemented)

```python
def browse_snapshot_content(self, repo_data, snapshot_id, password):
    """Browse files in a snapshot with search/filter"""
    args = ["-r", repo_data["path"], "ls", "--long", snapshot_id]
    env = {"RESTIC_PASSWORD": password}
    
    # Execute in background worker
    worker = ResticWorker(self.restic_cmd, args, env)
    worker.finished.connect(self.display_snapshot_files)
    worker.start()

def search_snapshot_files(self, search_text, filter_mode):
    """Search files with AND/OR operators"""
    # AND operator: term1 & term2 (all must match)
    # OR operator: term1 | term2 (any can match)
    
    if "&" in search_text:
        # AND search - all terms must be present
        terms = [t.strip().lower() for t in search_text.split("&")]
        for row in range(self.files_table.rowCount()):
            path = self.files_table.item(row, 0).text().lower()
            if filter_mode == "Contains":
                match = all(term in path for term in terms)
            else:  # Not Contains
                match = all(term not in path for term in terms)
            self.files_table.setRowHidden(row, not match)
    
    elif "|" in search_text:
        # OR search - any term can match
        terms = [t.strip().lower() for t in search_text.split("|")]
        for row in range(self.files_table.rowCount()):
            path = self.files_table.item(row, 0).text().lower()
            if filter_mode == "Contains":
                match = any(term in path for term in terms)
            else:  # Not Contains
                match = not any(term in path for term in terms)
            self.files_table.setRowHidden(row, not match)
```

### Lock Management (✅ Fully Implemented)

```python
def unlock_repository(self, repo_data, password):
    """Unlock repository after confirmation"""
    reply = QMessageBox.question(self, "Unlock Repository",
                                "Are you sure you want to unlock this repository?",
                                QMessageBox.StandardButton.Yes | 
                                QMessageBox.StandardButton.No)
    if reply == QMessageBox.StandardButton.Yes:
        args = ["-r", repo_data["path"], "unlock"]
        env = {"RESTIC_PASSWORD": password}
        success, stdout, stderr = self.restic_cmd.run(args, env)

def _auto_unlock_after_completion(self, repo_info):
    """Auto-unlock only if locks exist"""
    args = ["-r", repo_info["repo"]["path"], "list", "locks"]
    env = {"RESTIC_PASSWORD": repo_info["password"]}
    success, stdout, stderr = self.restic_cmd.run(args, env)
    
    # Only unlock if locks were found
    if success and stdout.strip():
        unlock_args = ["-r", repo_info["repo"]["path"], "unlock"]
        self.restic_cmd.run(unlock_args, env)
```

### Loading Snapshots (To Implement)

```python
def load_snapshots(self):
    repo = get_selected_repo()
    
    # Execute: restic -r <repo> snapshots --json
    args = ["-r", repo["path"], "snapshots", "--json"]
    env = {"RESTIC_PASSWORD": repo["password"]}
    
    success, stdout, stderr = self.restic_cmd.run(args, env)
    
    if success:
        snapshots = json.loads(stdout)
        # Populate table with snapshot data
```

### Creating Backups (To Implement)

```python
def start_backup(self):
    # Get repository and decrypt password
    repo_name = self.backup_repo_combo.currentText()
    repo, password = self.get_repository_by_name(repo_name)
    
    # Build command with all options
    args = ["-r", repo["path"], "backup"]
    
    # Add paths
    paths = [self.backup_paths_list.item(i).text() 
             for i in range(self.backup_paths_list.count())]
    args.extend(paths)
    
    # Add tags
    tags = [tag.strip() for tag in self.backup_tags_input.text().split(",") if tag.strip()]
    for tag in tags:
        args += ["--tag", tag]
    
    # Add exclude patterns
    exclude_patterns = self.backup_exclude_input.toPlainText().strip().split("\n")
    for pattern in exclude_patterns:
        if pattern.strip():
            args += ["--exclude", pattern.strip()]
    
    # Add advanced options (NEW)
    if self.exclude_caches_check.isChecked():
        args.append("--exclude-caches")
    
    if self.pack_size_spin.value() > 0:
        args += ["--pack-size", str(self.pack_size_spin.value())]
    
    if self.one_file_system_check.isChecked():
        args.append("--one-file-system")
    
    if self.exclude_if_present_input.text().strip():
        args += ["--exclude-if-present", self.exclude_if_present_input.text().strip()]
    
    # Set password environment variable
    env = {"RESTIC_PASSWORD": password}
    
    # Use ResticWorker thread for non-blocking execution
    worker = ResticWorker(self.restic_cmd, args, env)
    worker.finished.connect(self.on_backup_complete)
    worker.start()
```

### Applying Retention (To Implement)

```python
def apply_retention(self, dry_run=True):
    # Build forget command:
    # restic -r <repo> forget --keep-last N --keep-daily N [--dry-run]
    
    args = ["-r", repo_path, "forget"]
    if self.keep_last_spin.value() > 0:
        args += ["--keep-last", str(self.keep_last_spin.value())]
    if self.keep_daily_spin.value() > 0:
        args += ["--keep-daily", str(self.keep_daily_spin.value())]
    # ... add other keep policies
    
    if dry_run:
        args.append("--dry-run")
    
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
```

### Snapshot Operations (To Implement)

#### Forget (Delete) Snapshot
```python
def forget_snapshot(self):
    # restic -r <repo> forget <snapshot-id>
    args = ["-r", repo["path"], "forget", snapshot_id]
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
```

#### Prune Repository
```python
def prune_repository(self):
    # restic -r <repo> prune
    args = ["-r", repo["path"], "prune"]
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
```

#### Browse Snapshot Content
```python
def browse_snapshot_content(self):
    # restic -r <repo> ls <snapshot-id>
    args = ["-r", repo["path"], "ls", snapshot_id]
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
    # Parse stdout and display in file list
```

#### Diff Snapshots (✅ Fully Implemented)
```python
def diff_snapshots(self):
    """Show diff between selected snapshot and previous"""
    row = selected[0].row()
    
    # Snapshots in chronological order (oldest first)
    # Row 0 = oldest, Row N-1 = newest
    if row == 0:
        QMessageBox.information(self, "No Previous", 
                               "This is the oldest snapshot")
        return
    
    # Current snapshot (newer)
    snapshot_id = self.snapshots_table.item(row, 0).text()
    # Previous snapshot (older) - one row before
    prev_snapshot_id = self.snapshots_table.item(row - 1, 0).text()
    
    # Create dialog with output display
    dialog = QDialog(self)
    diff_output = QPlainTextEdit()
    diff_output.setFont(QFont("Consolas", 9))
    
    # Execute diff in background
    args = ["-r", repo["path"], "diff", prev_snapshot_id, snapshot_id]
    env = {"RESTIC_PASSWORD": password}
    
    worker = ResticWorker(self.restic_cmd, args, env, timeout=300)
    worker.finished.connect(lambda success, stdout, stderr: 
                          self._on_diff_completed(success, stdout, stderr, 
                                                 diff_output, stats_labels))
    worker.start()
    
    dialog.exec()

def _on_diff_completed(self, success, stdout, stderr, output_widget, 
                      added_label, modified_label, removed_label):
    """Display diff results with statistics"""
    output_widget.setPlainText(stdout if stdout else stderr)
    
    # Parse and display statistics
    added_count = output.count('\n+')
    modified_count = output.count('\nM')
    removed_count = output.count('\n-')
    
    # Color-code statistics
    added_label.setText(f"Added: {added_count}")
    added_label.setStyleSheet("color: #28a745; font-weight: bold;")
    modified_label.setText(f"Modified: {modified_count}")
    modified_label.setStyleSheet("color: #ffc107; font-weight: bold;")
    removed_label.setText(f"Removed: {removed_count}")
    removed_label.setStyleSheet("color: #dc3545; font-weight: bold;")
```

#### Repository Statistics
```python
def load_repository_stats(self):
    # restic -r <repo> stats
    args = ["-r", repo["path"], "stats"]
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
```

#### Verify Repository
```python
def verify_repository(self):
    # restic -r <repo> check --read-data
    args = ["-r", repo["path"], "check", "--read-data"]
    env = {"RESTIC_PASSWORD": password}
    success, stdout, stderr = self.restic_cmd.run(args, env)
```

## Key Design Decisions

1. **Settings Storage**: Simple JSON file (similar to your client_gui_full.py)
   - Added `backup_jobs` array for persistent job storage
   - Each job stores full configuration (paths, tags, excludes, advanced options)

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
7. **Implement Snapshot Table Loading**: Execute and parse `restic snapshots --json`
8. **Complete Restore Operations**: Implement file selection and restore execution
9. **Connect Forget/Prune**: Wire up snapshot deletion and repository pruning
10. **Add Scheduling**: Windows Task Scheduler automation for backup jobs

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
  - Utility scripts (check_machine_id.py, test_license.py)
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
2. **Request Machine ID**: Ask customer to run `check_machine_id.py` or copy from activation dialog
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
python check_machine_id.py
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
- `check_machine_id.py` - Machine ID checker
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
