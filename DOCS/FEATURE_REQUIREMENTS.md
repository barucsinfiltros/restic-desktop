### Potential Enhancements
1. **Dashboard Enhancements**: ✅ PARTIAL (Phase 1 Complete)
  - ✅ Display visual summaries (graphs or charts) for repository statuses - **IMPLEMENTED** (QPainter doughnut/bar charts)
    - ✅ Repository storage distribution (doughnut chart)
    - ✅ Snapshot counts per repository (rounded bar chart)
  - ⏳ Space usage over time - **PENDING** (requires historical data collection - Phase 2)
  - ⏳ Success/failure of scheduled backups visualization - **PENDING** (requires tracking system - Phase 2)

2. **Notification System**: ✅ COMPLETE
  - ✅ Desktop notifications for backup/job completion, failures - **IMPLEMENTED** (Windows toast notifications)
  - ⏳ Email notifications - **PENDING**
  - ⏳ Space warnings - **PENDING**

<!-- 3. **Advanced Retention Rules**:
  - Support for more granular retention strategies, like custom rules for specific tags or hosts. -->


5. **Cross-Platform Config Management**:
  - Feature to export/import settings, including repository configurations, backup jobs, and schedules.


7. **Cloud Backup Optimization**:
  - Automatically detect and optimize settings for cloud storage systems like B2, AWS S3 (e.g., multi-threading, checkpoint support).

8. **Backup Validation**:
  - Introduce a detailed verification system post-backup completion to ensure data integrity (e.g., hash checksum validation).



13. **Snapshot Metadata Comparison**:
   - Enhance the "Diff Snapshots" feature to not just include changes but also output an easy-to-read summary.

14. **Automated Upgrade Process**:
   - Build-in app upgrade functionality to fetch updates without manually downloading/installing.

15. **Enhanced Scheduling**:
   - Option to run backup jobs based on triggers other than time (e.g., repository changes, specific conditions in file systems).

