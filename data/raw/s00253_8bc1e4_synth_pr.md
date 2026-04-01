## Title: Fix signed/unsigned integer comparison mismatch in time_server_thread

### Summary
The time_server_thread function in the time_manager module contained a signed/unsigned integer comparison mismatch in its tick processing loop. The loop counter `i` was declared as a signed `int` while being compared against the unsigned `uint64_t` variable `ticks`. This mismatch could lead to incorrect branch behavior and potential undefined behavior when processing large tick values.

This fix changes the loop counter type from `int` to `uint64_t` to match the signedness of the `ticks` variable, ensuring proper comparison semantics and eliminating the type mismatch warning. While the issue was originally reported in the `time_server_tick_callback` function, the actual problematic comparison was identified in the `time_server_thread` function's tick processing logic.

### Changes
- `common/utils/time_manager/time_server.c`: Changed loop counter variable `i` from `int` to `uint64_t` in the tick processing loop at line 84 to match the type of the `ticks` variable it compares against.

### Testing
- Verified the change resolves the signed/unsigned comparison warning during compilation
- Confirmed the loop logic remains functionally identical with proper type alignment
- Ensured the fix does not alter the tick processing behavior or performance characteristics
- Validated that the time server continues to function correctly with various tick values