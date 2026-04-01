## Title: Fix missing mutex lock in RA response window state access

### Summary
Add missing pthread mutex protection around the critical section accessing shared random access state variables in the UE MAC layer. The code in `nr_ue_get_rach()` was directly manipulating shared RA state (including `RA_window_cnt`, `RA_backoff_indicator`, `RA_RAPID_found`, and `RA_BI_found`) without acquiring the module-level mutex, creating a race condition vulnerability in multi-threaded gNB deployments.

This change wraps the entire RA state access block with `pthread_mutex_lock(&mac->mutex)` and `pthread_mutex_unlock(&mac->mutex)` calls to ensure exclusive access to the shared random access context during response window processing and backoff calculations.

### Changes
- `openair2/LAYER2/NR_MAC_UE/nr_ra_procedures.c`: Added mutex lock before the critical section at line 765 and corresponding unlock at line 806, protecting all shared RA state accesses and modifications within the RA response window handling logic.

### Implementation Details
- Uses the existing `mac->mutex` synchronization primitive already defined in the MAC module structure
- The lock scope encompasses all shared state reads and writes, including backoff indicator processing, window countdown, and preamble collision detection
- Maintains the existing error handling paths; the unlock is positioned to execute regardless of conditional branches within the critical section

### Testing
- Verified compilation with OAI's NR UE MAC build configuration
- Code review confirms no early returns or branching paths that would bypass the new unlock call
- Static analysis shows proper pairing of lock/unlock operations within the function scope