## Title: Fix race condition in itti_get_task_name by adding missing mutex lock

### Summary
The `itti_get_task_name()` function in the ITTI (Inter-Task Communication Interface) subsystem accessed the global `tasks` array without acquiring the `lock_nb_queues` mutex. This created a race condition where concurrent reads from this function and writes from task management operations could lead to undefined behavior, including potential use-after-free or access to inconsistent data during task initialization or termination.

This fix adds proper synchronization by acquiring the mutex before accessing the shared `tasks` array and releasing it immediately after reading the task name. The critical section is kept minimal to reduce lock contention while ensuring thread-safe access to the shared state.

### Changes
- `common/utils/ocp_itti/intertask_interface.cpp`: Added `pthread_mutex_lock(&lock_nb_queues)` before accessing `tasks[task_id]->admin.name` and `pthread_mutex_unlock(&lock_nb_queues)` after reading the value in `itti_get_task_name()`.

### Implementation Details
The mutex is held only for the duration of the array access and string pointer retrieval, following the existing locking pattern used elsewhere in the ITTI subsystem. This ensures the fix is consistent with the codebase's concurrency model and minimizes performance impact.

### Testing
- Verified that the function still returns correct task names under normal operation
- Confirmed that the locking pattern matches other synchronized accesses to the `tasks` array in the same file
- No functional changes to the API or behavior, only thread safety improvement