## Title: Fix integer underflow in LOG subsystem buffer management

### Summary
The LOG subsystem's memory logging mechanism uses a double-buffering scheme controlled by the `log_mem_side` variable. When this signed integer was used in buffer switching arithmetic (e.g., `1-log_mem_side`), it could underflow if corrupted or improperly initialized, producing an unexpectedly large unsigned value downstream. This underflow risked out-of-bounds access to the `log_mem_d[2]` array and potential segmentation faults during high-throughput logging operations.

The root cause was the signed `int` type for `log_mem_side`, which allowed negative values that become large positive values when cast to unsigned for array indexing or arithmetic. This fix changes the type to `unsigned int` to ensure proper modulo arithmetic behavior and prevent underflow scenarios.

### Changes
- `common/utils/LOG/log.c`: Change declaration of `log_mem_side` from `static volatile int` to `static volatile unsigned int` to prevent integer underflow during buffer switching operations.

### Implementation Details
The `log_mem_side` variable toggles between 0 and 1 to select the active buffer in the `log_mem_d[2]` array. Operations like `1-log_mem_side` now reliably produce valid indices (0 or 1) without underflow risk. This is particularly important in the concurrent logging path where `flush_mem_to_file()` and `logInit_log_mem()` interact with this variable across thread boundaries.

### Testing
- Verified compilation succeeds without warnings
- Confirmed logging initialization completes successfully in both single-threaded and multi-threaded scenarios
- The change is minimal and type-safe, preserving existing logic while eliminating the underflow vulnerability