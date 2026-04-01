## Title: Fix race condition in UE BLER stats initialization

### Summary
Move initialization of UE BLER statistics before adding UE to connected list to eliminate a race condition between timer expiry handlers and message processing threads. Previously, `init_bler_stats()` was called after `add_UE_to_list()`, making the UE visible to other threads before its `bler_stats` structure was initialized. If a timer expired or message arrived for the UE during this window, concurrent access to uninitialized stats could cause undefined behavior or crashes. The fix reorders the initialization sequence to ensure all control structures are fully populated before the UE becomes accessible to other threads.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_primitives.c`: In `add_connected_nr_ue()`, moved `sched_ctrl` field initialization, `reset_srs_stats()`, and `init_bler_stats()` calls to occur **before** `NR_SCHED_LOCK()` and `add_UE_to_list()`. This guarantees thread-safe initialization by completing all setup while the UE object is still private to the calling thread.

### Implementation Details
The race window existed because `add_UE_to_list()` makes the UE globally visible immediately upon insertion into `UE_info->connected_ue_list`. Timer expiry handlers and message processors can then access `UE->UE_sched_ctrl.dl_bler_stats` and `ul_bler_stats` before `init_bler_stats()` sets their initial MCS, BLER target, and frame tracking state. The fix closes this window by moving initialization ahead of list insertion, with an explicit comment documenting the synchronization requirement.