## Title: Fix incorrect loop bounds validation in T tracer multi tool

### Summary
The T tracer multi tool (`multi.c`) had insufficient validation of length parameters read from network sockets before using them in loop bounds. This could cause iteration over invalid indices when processing trace event enable/disable commands, potentially leading to out-of-bounds memory access or crashes from malformed network input. This patch adds proper bounds checking for the `len` parameter before entering loops that access the event tracking arrays.

### Changes
- `common/utils/T/tracer/multi.c`: 
  - Added validation `if (len < 0 || len >= number_of_events)` before the loop at line 347 to ensure the iteration count is within safe bounds
  - Fixed off-by-one error in existing validation at line 358, changing `len > number_of_events` to `len >= number_of_events` for consistency
  - Both changes prevent potential buffer overflow when `len` is read from the network socket

### Implementation Details
The validation ensures `len` is non-negative and strictly less than `number_of_events` (not equal), matching the array bounds check used for individual indices within the loops. This defensive programming measure protects against corrupted or malicious network packets that could otherwise cause the tracer to access memory beyond the allocated `t_is_on` and `is_on` arrays. The fix maintains the existing error handling pattern by jumping to `tracer_error` label on invalid input.