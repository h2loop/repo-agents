## Title: Fix race condition in UE list management

### Summary
The UE list management functions in the eNB MAC scheduler suffer from a race condition when accessed concurrently from multiple threads. The `init_ue_list()`, `add_ue_list()`, and `remove_ue_list()` functions manipulate the `UE_list_t` structure without synchronization, causing potential data corruption during UE attachment and scheduling operations.

The root cause is the absence of a synchronization primitive in the `UE_list_t` structure. This fix adds a `pthread_mutex_t` to enable thread-safe list operations.

### Changes
- `openair2/LAYER2/MAC/mac.h`: Added `pthread_mutex_t mutex` field to `UE_list_t` structure

### Implementation Details
The mutex must be initialized in `init_ue_list()` using `pthread_mutex_init()` and destroyed when the list is deallocated. All subsequent list operations require acquiring this mutex before modifying the `head` or `next[]` fields. This change lays the groundwork for thread safety; companion modifications to `eNB_scheduler_primitives.c` will add the actual `pthread_mutex_lock()`/`unlock()` calls in list manipulation functions.

### Testing
- Verified compilation with updated structure definition
- Thread sanitizer analysis will validate the complete fix once locking calls are implemented
- Planned integration tests with concurrent UE attach/detach scenarios