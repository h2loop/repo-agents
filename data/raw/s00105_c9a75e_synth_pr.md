## Title: Add mutex protection for PUCCH2 shared lookup tables

### Summary
The `init_pucch2_luts()` function initializes static lookup tables (LUTs) used for PUCCH2 decoding without any synchronization mechanism. These LUTs are shared global state accessed by multiple threads, creating a race condition where concurrent initialization or simultaneous read/write access could corrupt data structures and lead to undefined behavior.

This change introduces a static mutex to protect both the initialization and read access paths for the PUCCH2 LUTs. The mutex ensures that LUT initialization completes atomically and that read operations during decoding are isolated from potential concurrent modifications.

### Changes
- `openair1/PHY/NR_TRANSPORT/pucch_rx.c`:
  - Added `#include <pthread.h>` for mutex primitives
  - Added static mutex `pucch2_lut_mutex` to protect all LUT access
  - Wrapped LUT initialization loop in `init_pucch2_luts()` with `pthread_mutex_lock/unlock`
  - Wrapped LUT read access loop in `nr_decode_pucch2()` with `pthread_mutex_lock/unlock`

### Implementation Details
The mutex is initialized statically using `PTHREAD_MUTEX_INITIALIZER` to ensure it's valid before any concurrent access can occur. The critical sections are kept minimal: in `init_pucch2_luts()` the lock covers the entire initialization sequence, and in `nr_decode_pucch2()` the lock covers the correlation loop that reads from the LUTs. This prevents race conditions while minimizing contention on the decode path.

### Testing
- Verified successful compilation with pthread library linkage
- Confirmed mutex lock/unlock pairs are properly matched in all code paths
- No functional behavior changes; this is a concurrency safety enhancement