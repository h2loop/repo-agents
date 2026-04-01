## Title: Fix resource leaks in shared memory creation function

### Summary
The `create_shm()` function in the gNB tracer application had resource management issues where file descriptors and shared memory segments could leak on error paths. The function opened a file with `open()` but never closed the file descriptor, and on failure conditions (ftok error, shmget failure, shmat failure), it would call `err_exit()` without proper cleanup. This could lead to resource exhaustion in long-running processes and left shared memory segments orphaned when attachment failed.

This patch ensures proper resource cleanup on all code paths by tracking and explicitly closing the file descriptor before every error exit, and by properly cleaning up shared memory segments when `shmat()` fails.

### Changes
- `common/utils/T/tracer/t_tracer_app_gnb.c`: Refactored `create_shm()` function to:
  - Store and manage the file descriptor from `open()` for explicit cleanup
  - Add `close(fd)` on all error paths before calling `err_exit()`
  - Improve shared memory cleanup logic when `shmat()` fails
  - Fix typo: "memeory" → "memory" in error message
  - Add additional error checking for existing shared memory segment retrieval

### Implementation Details
The function now uses local variables to track resources (`fd`, `key`, `shm_id`, `addr`) and follows a consistent cleanup pattern: on any error after successfully opening the file, `close(fd)` is called before exiting. When `shmat()` fails, the code now attempts to remove the shared memory segment with `shmctl()` before closing the file descriptor and exiting, preventing orphaned segments.

### Testing
- Code review confirms all error paths now properly clean up resources
- Static analysis shows no remaining resource leaks in the modified function
- Verified that successful path still closes file descriptor after operations complete