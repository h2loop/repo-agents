## Title: Fix hash table resize atomicity to prevent signaling procedure violations

### Summary
The `hash_table_resize` function in the OMG subsystem lacked proper error handling and atomicity guarantees. During resize operations, if `hash_table_add` failed while re-adding elements to the new store house, the hash table could be left in an inconsistent state with partially migrated data and incorrect mode settings. This corrupted state propagated downstream, causing signaling procedure sequences that violated 3GPP message flow expectations.

The fix implements a complete rollback mechanism that preserves the original hash table state before any modifications. If any step fails during resize (memory allocation or re-adding elements), the function now restores the original store house, key count, and mode, then returns an error code. This ensures the hash table remains in a valid state at all times, preventing cascading signaling violations.

### Changes
- `openair2/UTIL/OMG/omg_hashtable.c`: Enhanced `hash_table_resize()` with comprehensive error handling and atomicity:
  - Save original state (store_house pointer, key_num, key_count) before modifications
  - Initialize elements pointer to NULL and add result tracking variable
  - Check return value of each `hash_table_add` call during element re-insertion
  - Implement rollback path: if re-addition fails, clean up new store house, restore original state, and free resources
  - Convert decrementing while-loop to standard incrementing for-loop for clarity
  - Ensure proper cleanup of elements array in all code paths

### Implementation Details
The critical improvement is the failure handling during the element re-addition phase. Previously, a failure mid-migration would leave the hash table in an undefined state. Now, the function tracks how many elements were successfully added before a failure, deletes those elements from the new store house, frees the new allocation, and fully restores the original table configuration. This atomicity guarantee ensures downstream components always interact with a consistent hash table state.