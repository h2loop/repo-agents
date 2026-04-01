## Title: Fix unreachable code path in RU MBSFN configuration update logic

### Summary
The RU control thread contains unreachable code after the first MBSFN configuration update. The conditional `fp->num_MBSFN_config != ru_sf_update` only detected changes in the number of MBSFN configurations. Once synchronized, this condition permanently evaluated to false, preventing subsequent updates even when MBSFN parameters changed. This caused remote RU units to miss configuration updates, potentially leading to subframe allocation mismatches.

This patch introduces proper change detection by checking both the configuration count and the actual MBSFN subframe configuration data. The fix ensures `send_update_rru()` is called whenever the MBSFN configuration changes, not just when the count changes.

### Changes
- `executables/ru_control.c`: Modified the MBSFN configuration change detection logic in `ru_thread_control()` around line 520.

### Implementation Details
- Added a `config_changed` flag that triggers on either:
  - MBSFN configuration count mismatch (`fp->num_MBSFN_config != ru_sf_update`)
  - MBSFN subframe configuration data changes (by comparing `mbsfn_SubframeConfig` fields in a loop)
- The update condition now depends on `config_changed` rather than just count mismatch
- This ensures the code path remains reachable for all configuration updates, not just the first one

### Testing
- Verified RU configuration updates trigger correctly when MBSFN subframe patterns change
- Confirmed the code path remains reachable for subsequent updates after initial synchronization
- Tested with remote IF5 interface to ensure proper RAU/RRU configuration exchange