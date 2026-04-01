## Title: Fix buffer overflow vulnerability in tracer XY view initialization

### Summary
The `new_view_xy()` function in the tracer utility did not validate the `length` parameter before allocating internal coordinate buffers. When called with zero or negative length, `calloc(length, sizeof(float))` could produce undefined behavior or buffer overflow conditions. This vulnerability could be triggered by malformed configuration or invalid API usage, potentially causing memory corruption in gNB deployments with tracing enabled.

This fix adds explicit validation of the `length` parameter immediately after allocating the main structure and before any buffer allocation. If an invalid length (≤ 0) is detected, the function prints a clear diagnostic message and aborts cleanly, preventing the vulnerable code path from executing.

### Changes
- `common/utils/T/tracer/view/xy.c`: Added parameter validation check in `new_view_xy()` after struct allocation. Invalid lengths now trigger early failure with descriptive error output before x/y buffer allocation occurs.

### Implementation Details
The validation is placed at lines 117-122, after `struct xy` allocation but before the `calloc()` calls for `ret->x` and `ret->y`. This ensures:
1. The `ret` structure is available for potential future cleanup paths
2. All buffer allocations are protected by the validation
3. Error messages include file, line, function name, and invalid value for debugging

### Testing
- Static analysis confirms the validation precedes all buffer allocations
- Code review verifies no valid use cases are impacted
- The fix maintains existing API behavior for valid positive lengths