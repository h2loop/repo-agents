## Title: Fix blocking RTOS API calls in interrupt context for inode operations

### Summary
This PR resolves an issue where blocking RTOS APIs were being called from interrupt context in the VFS `chstat`/`lchmod` code path. The problem occurs in `inode_find()`, which calls `inode_rlock()` and `inode_runlock()`—both of which use blocking semaphore operations (`down_read`/`up_read`). Calling these from interrupt context leads to undefined behavior or system deadlock.

The fix introduces non-blocking variants of the inode locking functions (`inode_trylock` and `inode_tryrlock`) and modifies `inode_find()` to detect interrupt context using `up_interrupt_context()`. When in interrupt context, the function uses the non-blocking variants and returns `-EWOULDBLOCK` if the lock cannot be acquired immediately.

### Changes
- `fs/inode/fs_inode.c`: Added `inode_trylock()` and `inode_tryrlock()` functions for non-blocking inode locking.
- `fs/inode/fs_inodefind.c`: Modified `inode_find()` to detect interrupt context and use non-blocking locks to prevent unsafe blocking calls.

### Testing
- Verified that `lchmod` and related VFS functions no longer trigger blocking calls from interrupt context.
- Confirmed correct behavior under both normal and interrupt contexts with test cases.