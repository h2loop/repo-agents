## Title: Fix race condition in LTE UL SCH gold unscrambling

### Summary
Fix a race condition in the LTE uplink shared channel (UL-SCH) decoding path where the `lte_gold_unscram` function was modifying shared state through a pointer parameter without synchronization. Multiple threads calling this function concurrently could corrupt the `x2` LFSR state variable, leading to incorrect descrambling and potential decoding failures.

The root cause was that `lte_gold_unscram` accepted a pointer to `x2` and updated it on each call, making it unsafe for concurrent access. This patch eliminates the shared state by making the LFSR state thread-local.

### Changes
- `openair1/PHY/LTE_TRANSPORT/ulsch_decoding.c`: 
  - Modified `lte_gold_unscram` signature to accept `x2` by value instead of by pointer
  - Added `static __thread unsigned int x2_state` to maintain per-thread LFSR state
  - Updated caller in `ulsch_decoding` to pass a thread-local copy of `x2`
  - Ensured reset path initializes thread-local state from the input parameter

### Implementation Details
The fix uses the `__thread` storage class to create thread-local storage for the LFSR state. On reset, the function initializes its thread-local `x2_state` from the input parameter. Subsequent iterations update only the thread-local copy, eliminating all shared mutable state. The caller passes `x2` by value to avoid any possibility of accidental aliasing.

### Testing
- Verified correct descrambling behavior with single-threaded operation
- Confirmed no data races detected under ThreadSanitizer with multi-threaded eNB configuration
- Validated UL throughput and BLER performance matches pre-fix baseline in `lte-softmodem` CI tests