## Title: Fix error propagation in FCB getnext function

### Summary
The `fcb_getnext_nolock()` function in the Flash Circular Buffer (FCB) subsystem was incorrectly returning success (`0`) even when flash read operations failed. When `fcb_elem_info()` returned errors such as `-EIO` from a failed `fcb_flash_read()`, the function would eventually return `0` instead of propagating the error code. This could cause callers to incorrectly assume a valid entry was found when the flash hardware had actually failed, potentially leading to data corruption or use of uninitialized memory.

The fix changes all `return 0;` statements to `return rc;` so that any error encountered during iteration is properly returned to the caller. Since `rc` is guaranteed to be `0` when those return statements are reached in the success path, the behavior for successful operations remains unchanged.

### Changes
- `subsys/fs/fcb/fcb_getnext.c`: Modified `fcb_getnext_nolock()` to return `rc` instead of hardcoded `0`, ensuring errors from `fcb_elem_info()` and `fcb_getnext_in_sector()` are propagated to callers.

### Testing
- Verified that successful FCB iteration still returns `0` after the change.
- Confirmed error codes from flash read failures are now properly returned instead of being silently swallowed.