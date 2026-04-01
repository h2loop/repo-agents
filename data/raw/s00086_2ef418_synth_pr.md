## Title: Fix missing mandatory IEs and uninitialized fields in NAS TEST AS simulator

### Summary
The NAS TEST AS simulator was generating malformed signaling messages due to missing mandatory information elements and uninitialized nested structures. Specifically:

1. **Missing mandatory `asCause` field**: The `process_nas_establish_req()` function failed to populate the `asCause` field in the `as_nas_establish_ind` message, violating the protocol specification and causing downstream parsing errors.

2. **Uninitialized nested message structures**: Three message processing functions (`process_nas_establish_req`, `process_ul_info_transfer_req`, and `process_nas_establish_rsp`) did not initialize the `length` and `data` fields of nested NAS message structures before conditional allocation. This led to undefined behavior when the allocation path was skipped, as receivers would encounter garbage values in these fields.

3. **Timestamp buffer vulnerability**: The `getTime()` function used a 16-byte buffer that was insufficient for the formatted timestamp string under certain conditions, and lacked error handling for `clock_gettime()` failures.

### Changes
- `openair3/NAS/TEST/AS_SIMULATOR/as_data.c`: 
  - Increased `TIME_BUFFER_SIZE` from 16 to 32 bytes to prevent overflow
  - Added error checking for `clock_gettime()` with fallback timestamp "0:000000"
  - Fixed format string from `%.6ld:%.6ld` to `%ld:%06ld` for consistent zero-padding

- `openair3/NAS/TEST/AS_SIMULATOR/as_process.c`:
  - Added `ind->asCause = req->cause;` in `process_nas_establish_req()` to set the mandatory cause field
  - Initialized all nested NAS message structures (`initialNasMsg`, `nasMsg`) with `length = 0` and `data = NULL` before conditional allocation blocks

### Testing
- Verified NAS establishment procedures complete without protocol errors in the AS simulator test harness
- Confirmed message structure integrity using the `nas_message_parser` validation tool
- Ran `as_simulator` unit tests to ensure no regressions in message generation paths