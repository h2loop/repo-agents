## Title: Add validation checks to NR tracer event handlers

### Summary
The NR event handler functions in the MAC PDU tracer lacked validation checks for uninitialized field indices. The functions `nr_ul`, `nr_dl`, `nr_dl_retx`, `nr_mib`, and `nr_rar` access event field arrays using indices that are initialized to -1 during data structure setup. Without validation, if the format parsing fails or fields are missing, these indices remain at -1, leading to invalid memory access when dereferencing `e.e[-1]`. This could cause segmentation faults or undefined behavior when processing malformed or incomplete trace events.

The fix adds early-return checks in each NR handler to verify that all required field indices have been properly set (not -1) before accessing the event data structures. This prevents crashes and makes the tracer more robust against missing or misconfigured trace fields.

### Changes
- `common/utils/T/tracer/macpdu2wireshark.c`: Added validation checks in `nr_ul()`, `nr_dl()`, `nr_dl_retx()`, `nr_mib()`, and `nr_rar()` functions to return early if any required field index is uninitialized (-1), preventing invalid memory access.

### Testing
- Verified tracer functionality remains correct with valid trace data
- Confirmed that missing fields no longer cause crashes during event processing