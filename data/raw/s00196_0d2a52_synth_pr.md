## Title: Fix race condition and deadlock in LTE scrambling LUT initialization

### Summary
The `init_scrambling_lut()` and `init_unscrambling_lut()` functions in the LTE downlink scrambling module were not thread-safe, causing race conditions and potential deadlocks when multiple PHY threads initialized the global lookup tables concurrently. The functions populate large static arrays (`scrambling_lut` and `unscrambling_lut`) used for bit-level scrambling operations, but lacked synchronization primitives to prevent concurrent initialization.

This patch implements a thread-safe double-checked locking pattern for both initialization functions. Static pthread mutexes guard the initialization sections, and static flags track completion state to avoid redundant initialization overhead. This ensures the LUTs are initialized exactly once, eliminating the race condition while minimizing performance impact on subsequent calls.

### Changes
- `openair1/PHY/LTE_TRANSPORT/dlsch_scrambling.c`: 
  - Added static mutexes (`scrambling_lut_mutex`, `unscrambling_lut_mutex`) and initialization flags
  - Wrapped LUT population loops in double-checked locking pattern in both `init_scrambling_lut()` and `init_unscrambling_lut()`
  - Added `#include <pthread.h>` for mutex primitives

### Implementation Details
The fix uses the standard double-checked locking idiom: a fast path check of the initialization flag avoids lock acquisition on every call, while the slow path acquires the mutex and re-checks the flag to prevent multiple threads from performing initialization. This is critical for performance since these functions are called frequently during PHY processing.

### Testing
- Verified thread-safe initialization under concurrent access from multiple eNB PHY threads
- Confirmed no regression in scrambling/unscrambling correctness via bit-exact validation against known test vectors
- Ran multi-cell simulation with 4 eNB instances to stress-test concurrent initialization paths