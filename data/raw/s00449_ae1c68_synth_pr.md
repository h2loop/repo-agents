## Title: Fix incorrect system call flags and time retrieval in UE tracer

### Summary
The UE tracer application contained several bugs related to incorrect system call flags and deprecated time retrieval functions. The `open()` call for shared memory creation lacked the `O_RDWR` flag, leading to potential permission issues. The `gettimeofday()` function was deprecated and less precise than modern alternatives. Additionally, the shared memory attachment logic used incorrect parameters when handling pre-existing segments, and the microsecond timestamp field had an insufficient data type that could overflow.

### Changes
- `common/utils/T/tracer/t_tracer_app_ue.c`: 
  - In `create_shm()`: Added `O_RDWR` flag to `open()` call to ensure proper read/write access when creating shared memory files. Fixed `shmget()` call in the EEXIST error path to include `SHMSIZE` and `IPC_CREAT` flags for correct shared memory attachment.
  - In `get_time_stamp_usec()`: Replaced deprecated `gettimeofday()` with `clock_gettime(CLOCK_REALTIME)` for improved precision and modern API compliance. Changed microsecond extraction from `tv.tv_usec` to `ts.tv_nsec / 1000` to correctly convert nanoseconds. Increased `usec` variable type from `uint16_t` to `uint32_t` to prevent overflow.

### Implementation Details
The timestamp conversion now properly handles nanosecond resolution by dividing by 1000, providing accurate microsecond timestamps for UE trace logging. The shared memory fixes ensure robust operation when the tracer restarts and encounters existing shared memory segments.

### Testing
- Verified successful compilation with strict warning flags
- Confirmed tracer initializes shared memory correctly on first run and subsequent runs
- Validated timestamp accuracy and format in generated trace logs