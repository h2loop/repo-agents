## Title: Fix scheduling priority inversion in NAS user simulator receive thread

### Summary
The NAS user simulator's receive thread was created without proper priority configuration, causing scheduling priority inversion where lower-priority tasks could preempt this critical signaling thread. The manual pthread creation using `pthread_attr_init()` and related calls bypassed the OpenAirInterface (OAI) centralized priority management system, leading to undefined scheduling behavior under load.

This change replaces the manual pthread setup with the standard `threadCreate()` wrapper, which integrates with OAI's real-time priority framework. The receive thread is now assigned `OAI_PRIORITY_RT_LOW`, ensuring it runs at the appropriate priority level relative to other NAS and RRC threads, eliminating the inversion issue.

### Changes
- `openair3/NAS/TEST/USER/user_simulator.c`: 
  - Replace manual `pthread_attr_init()`, `pthread_attr_setscope()`, `pthread_attr_setdetachstate()`, and `pthread_create()` sequence with `threadCreate(&thread_id, _receive_thread, NULL, "NAS_TEST_USER_RX", -1, OAI_PRIORITY_RT_LOW)`
  - Fix header include path from `"include/commonDef.h"` to `"commonDef.h"` for consistency
  - Add `#include <common/utils/system.h>` for `threadCreate()` prototype

### Implementation Details
The `threadCreate()` wrapper automatically handles thread attribute configuration, scheduling policy, and priority inheritance through the OAI runtime system. The thread name "NAS_TEST_USER_RX" enables better debugging via `top` and OAI logs. The `-1` parameter uses default CPU affinity, while `OAI_PRIORITY_RT_LOW` places the receive thread at a proper priority level above normal tasks but below critical path threads.