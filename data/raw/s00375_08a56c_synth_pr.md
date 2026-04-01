## Title: Fix race condition in TimeZoneAndTime XML debug output

### Summary
The `dump_time_zone_and_time_xml` function in the NAS TimeZoneAndTime IE module had a race condition between timer expiry handlers and normal message processing threads. Both code paths could call this debug function concurrently, resulting in interleaved stdout output and corrupted XML formatting. This patch adds proper synchronization to serialize access to the shared output resource.

The race occurred because the function performs multiple printf calls without atomicity guarantees. When timer-based events and regular message processing overlapped, the XML output from different contexts would mix, making debug logs unreadable and potentially causing output buffer corruption.

### Changes
- `openair3/NAS/COMMON/IES/TimeZoneAndTime.c`: 
  - Added `#include <pthread.h>` for synchronization primitives
  - Introduced a static mutex `dump_mutex` initialized with `PTHREAD_MUTEX_INITIALIZER`
  - Wrapped the entire function body of `dump_time_zone_and_time_xml` with `pthread_mutex_lock()` and `pthread_mutex_unlock()` to ensure exclusive access during XML formatting and output

### Implementation Details
The fix uses a simple static mutex to provide coarse-grained locking around the entire debug dump operation. This approach is appropriate because:
- The function is debug-only (called only when `NAS_DEBUG` is defined)
- The critical section is short and I/O-bound
- It prevents any interleaving of XML tags between concurrent callers
- No deadlock risk as the function has no internal recursion or complex lock ordering

The mutex is statically initialized for reliability and minimal startup overhead. Performance impact is negligible since this code path is only active in debug builds.