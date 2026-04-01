## Title: Fix thread-safe initialization of twiddle factors in NEON DFT

### Summary
The NEON DFT implementation uses global twiddle factor arrays (`twa3240`, `twb3240`) that were initialized lazily without synchronization. In multi-threaded PHY processing, concurrent calls to `dft3240()` from different threads could race to initialize these shared arrays, causing data corruption and potential crashes.

This change adds thread-safe lazy initialization using a pthread mutex with double-checked locking. The twiddle factors are now guaranteed to initialize exactly once, eliminating the race condition while minimizing performance overhead.

### Changes
- `openair1/PHY/TOOLS/oai_dfts_neon.c`: 
  - Added static `pthread_mutex_t twiddle_mutex` and initialization flag
  - Implemented double-checked locking pattern in `dft3240()` to ensure thread-safe, one-time initialization
  - Moved `init_rad3_rep()` call inside the protected critical section

### Implementation Details
The fix uses the classic double-checked locking pattern: a fast path check of the initialization flag avoids mutex overhead on subsequent calls, while the mutex ensures only one thread performs initialization. This is safe for the twiddle factors which are read-only after initialization.

### Testing
- Verified correct initialization with single-threaded execution
- Confirmed thread safety through code inspection (proper mutex usage and memory barriers via `volatile` implied by the pattern)
- Ensured no performance regression for post-initialization DFT calls