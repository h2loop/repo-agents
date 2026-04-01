## Title: Add missing parameter validation to obj_hashtable_remove

### Summary
The `obj_hashtable_remove` function in the common hashtable utility lacked comprehensive parameter validation before processing protocol messages downstream. While it checked for a NULL hashtable pointer, it failed to validate the key pointer, key size, nodes array, or hash function pointer. Passing NULL for `keyP` or `hashfunc`, a non-positive `key_sizeP`, or operating on a hashtable with uninitialized nodes could lead to undefined behavior, segmentation faults, or potential security vulnerabilities through invalid memory access.

The fix adds explicit validation checks for all critical parameters before any pointer dereferencing or arithmetic operations. Each invalid state returns the existing `HASH_TABLE_BAD_PARAMETER_HASHTABLE` error code to maintain consistent error handling throughout the hashtable API.

### Changes
- `common/utils/hashtable/obj_hashtable.c`: Added validation checks in `obj_hashtable_remove()` for:
  - `keyP == NULL`
  - `key_sizeP <= 0`
  - `hashtblP->nodes == NULL`
  - `hashtblP->hashfunc == NULL`

### Testing
- Verified that invalid parameter combinations now return appropriate error codes instead of crashing
- Confirmed that valid operations continue to function correctly with the new guards in place
- Reviewed call sites to ensure they properly handle the `HASH_TABLE_BAD_PARAMETER_HASHTABLE` return code