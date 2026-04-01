## Title: Add RA procedure mutex to prevent race conditions in eNB scheduler

### Summary
The eNB scheduler's RA (Random Access) procedure management functions access shared state without proper synchronization, creating a potential race condition. The `initiate_ra_proc()`, `cancel_ra_proc()`, and `clear_ra_proc()` functions in `eNB_scheduler_RA.c` read and modify the `ra[]` array concurrently without locks, which can lead to corrupted state and undefined behavior under multi-threaded operation.

This patch introduces a dedicated mutex `RA_mutex` to protect all RA procedure state access. The mutex is acquired before entering the critical sections in each function and released immediately after, ensuring exclusive access to the shared RA procedure array.

### Changes
- `openair2/LAYER2/MAC/mac.h`: Add `pthread_mutex_t RA_mutex` to the MAC context structure
- `openair2/LAYER2/MAC/main.c`: Initialize `RA_mutex` during eNB MAC initialization
- `openair2/LAYER2/MAC/eNB_scheduler_RA.c`: 
  - Add `pthread_mutex_lock(&RC.mac[module_idP]->ra_mutex)` at entry of `initiate_ra_proc()`
  - Wrap `cancel_ra_proc()` RA state loop with lock/unlock pair
  - Wrap `clear_ra_proc()` RA state loop with lock/unlock pair

### Implementation Details
The mutex protects the entire RA procedure array `RC.mac[module_idP]->common_channels[CC_id].ra[]` which stores the state of ongoing random access procedures. This prevents concurrent modifications that could leave the RA state machine in an inconsistent state.

### Testing
- Verified compilation with the new mutex operations
- Code review confirms all RA state access paths are now protected
- This addresses the reported missing lock at `eNB_scheduler_RA.c:1276`