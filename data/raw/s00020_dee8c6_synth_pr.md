## Title: Add mutex protection for VCD signal dumper FIFO operations

### Summary
The VCD signal dumper functions `vcd_signal_dumper_dump_variable_by_name()` and `vcd_signal_dumper_dump_function_by_name()` were accessing shared FIFO state without synchronization, creating a race condition when multiple threads log signals concurrently. The shared `vcd_fifo` structure and its write index could be corrupted, leading to lost trace data or undefined behavior.

This patch introduces a global mutex to protect the critical section where the FIFO write index is obtained and the shared memory entry is populated. The implementation ensures thread-safe VCD tracing while maintaining minimal performance overhead by keeping the lock duration as short as possible.

### Changes
- `common/utils/LOG/vcd_signal_dumper.c`: 
  - Added `pthread_mutex_t vcd_mutex` global variable (statically initialized)
  - Wrapped FIFO write operations in `vcd_signal_dumper_dump_variable_by_name()` with mutex lock/unlock pair
  - Wrapped FIFO write operations in `vcd_signal_dumper_dump_function_by_name()` with mutex lock/unlock pair

### Implementation Details
The mutex protects the sequence:
1. Getting the FIFO write index via `vcd_get_write_index()`
2. Writing timestamp, data payload, and module identifier to `vcd_fifo.user_data[write_index]`
3. Setting the `module` field last to atomically validate the entry

The lock is held only for these operations and released immediately after, following the principle of minimizing the critical section. The `PTHREAD_MUTEX_INITIALIZER` ensures the mutex is properly initialized before first use.

### Testing
- Verified VCD trace generation remains functional in both single-threaded and multi-threaded scenarios
- Confirmed no performance regression in high-frequency signal dumping paths
- Validated that concurrent calls from multiple threads no longer corrupt FIFO state