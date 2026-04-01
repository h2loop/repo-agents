## Title: Fix mutex deadlock in WLS memory allocation error path

### Summary
Fix a concurrency bug in the WLS (Wireline Simulation) integration layer that could cause F1AP interface message loss or corruption. In `wls_mac_alloc_buffer()`, when memory allocation fails, the function was calling `wls_mac_print_stats()` while still holding the `lock_alloc` mutex. This violates proper lock discipline and can lead to deadlocks when other threads attempt to acquire the same lock during stats printing operations. The issue particularly impacts F1AP message handling between CU and DU components, where timing-sensitive operations cannot tolerate unexpected lock contention.

This patch resolves the issue by releasing the mutex before invoking the stats printing function, ensuring that lock-protected data structures remain accessible to other threads during error diagnostics.

### Changes
- `nfapi/oai_integration/wls_integration/wls_vnf.c`: Reordered operations in the error path of `wls_mac_alloc_buffer()` to call `pthread_mutex_unlock()` before `wls_mac_print_stats()`, preventing lock retention during potentially blocking debug output.

### Implementation Details
- The fix is minimal and surgical, affecting only the error handling branch where `wls_mac_alloc_mem_array()` returns non-zero
- Successful allocation paths remain unchanged
- Maintains thread safety by ensuring the lock is never held across function calls that may acquire other locks or perform I/O
- No changes to function signatures or data structures

### Testing
- Verified the change does not alter successful memory allocation behavior
- Code inspection confirms the lock is now properly released before any potentially blocking operations
- Recommended: Run F1AP interface stress tests under memory pressure conditions to validate deadlock resolution