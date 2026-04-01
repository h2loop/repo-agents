## Title: Fix race condition in Bluetooth mesh scanning state management

### Summary
This PR resolves a race condition in the Bluetooth mesh advertising subsystem where the shared `active_scanning` flag was accessed and modified by multiple threads without synchronization. This could lead to inconsistent scan states and unpredictable behavior when multiple threads attempted to change the scanning mode concurrently.

The fix introduces a mutex (`scan_mutex`) to protect all accesses to the `active_scanning` variable, ensuring thread-safe read and write operations. Functions `bt_mesh_scan_active_set()` and `bt_mesh_scan_enable()` have been updated to use this mutex when accessing the shared state.

### Why
Without proper synchronization, concurrent access to the `active_scanning` variable could cause:
- Inconsistent scan parameter configuration
- Unexpected scan behavior
- Potential system instability in multithreaded environments

### Changes
- **subsys/bluetooth/mesh/adv.c**: 
  - Added `scan_mutex` for protecting `active_scanning` variable
  - Modified `bt_mesh_scan_active_set()` to use mutex for thread-safe access
  - Updated `bt_mesh_scan_enable()` to safely read scanning state under mutex protection

### Testing
Verified that scanning functionality works correctly with mutex protection in place, maintaining backward compatibility while eliminating race conditions. Tested with sequential and concurrent calls to scanning state modification functions.