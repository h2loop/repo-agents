## Title: Add mutex protection to IMSI mobile identity decoding

### Summary
The `decode_imsi_mobile_identity` function in the NAS COMMON IES subsystem accesses shared state during IMSI decoding without synchronization primitives. This creates a race condition vulnerability in multi-threaded environments where multiple UE contexts may be processed concurrently, potentially leading to corrupted IMSI parsing or state inconsistencies.

This patch adds a pthread mutex to protect the critical section in the IMSI decoding path. The mutex ensures that only one thread can execute the IMSI mobile identity decoding logic at a time, preventing concurrent access to shared resources and maintaining data integrity during NAS message processing.

### Changes
- `openair3/NAS/COMMON/IES/MobileIdentity.c`: 
  - Added `#include <pthread.h>` for mutex primitives
  - Added static mutex `mobile_identity_mutex` with static initialization
  - Wrapped the IMSI decoding logic with `pthread_mutex_lock()` and `pthread_mutex_unlock()`
  - Ensured mutex is released on all exit paths, including error conditions

### Implementation Details
The mutex is implemented as a file-static variable initialized with `PTHREAD_MUTEX_INITIALIZER` for lock-free initialization. The lock is acquired immediately after the local variable declaration in `decode_imsi_mobile_identity()` and is explicitly released before each return statement. This fine-grained locking approach minimizes the critical section duration while ensuring complete protection of the shared state accessed during IMSI digit extraction and validation. The implementation follows the existing mutex patterns used elsewhere in the NAS COMMON UTIL subsystem.