## Title: Fix race condition in unicast client stop callback by adding mutex protection

### Summary
This PR resolves a race condition in the `unicast_client_stop_cb` function and other related callbacks in the BAP unicast audio tester code. The issue occurred due to unsynchronized access to shared stream data (`ase_id`, `cis_id`) from multiple threads or interrupt contexts. Under certain timing conditions, this could lead to data corruption or inconsistent state reporting.

The fix introduces a mutex (`connections_mutex`) to protect all accesses to shared unicast stream fields. All functions that read from or write to these fields now use proper locking to ensure thread safety.

### Changes
- **tests/bluetooth/tester/src/audio/btp_bap_unicast.c**: 
  - Added `connections_mutex` for synchronizing access to shared stream data
  - Protected `ase_id` and `cis_id` accesses in `btp_send_ascs_cis_connected_ev`, `btp_send_ascs_cis_disconnected_ev`, and `stream_state_changed` callbacks
  - Used local variables to minimize lock hold time

### Why
Race conditions were occurring when multiple Bluetooth events (like stream state changes or CIS connections) happened concurrently, leading to potential data corruption in the test framework's event reporting. This fix ensures deterministic behavior and prevents intermittent test failures.

### Testing
Verified with Zephyr Bluetooth tester framework under concurrent connection scenarios. No regressions observed in existing BAP test cases.