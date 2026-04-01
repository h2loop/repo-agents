## Title: Fix 5GMM timer handling on authentication reject

### Summary
The NAS UE implementation did not properly stop running 5GMM timers when receiving an Authentication Reject message from the network. This violated 3GPP TS 24.501 protocol requirements and could lead to timer expiry events firing after authentication failure, causing undefined behavior and potential state machine corruption. This patch ensures all active 5GMM timers are stopped when authentication is rejected.

### Changes
- `openair3/NAS/NR_UE/ue_process_nas.c`: 
  - Implement `SGSauthenticationReject()` handler to process authentication reject messages
  - Add `_stop_all_running_timers()` function that stops T3510, T3516, T3517, T3519, and T3520 timers
  - Clear security context and mark USIM as invalid after timer cleanup
  - Add required includes: `emmData.h`, `nas_timer.h`, `emm_timers.h`

### Implementation Details
The timer stop operations are performed before clearing security context to prevent race conditions. Each timer stop is logged for debugging purposes. The implementation follows 3GPP TS 24.501 Section 5.4.2.5 requirements for UE behavior on authentication failure.

### Testing
- Manual test: Trigger authentication reject from test AMF, verify all timers stopped and no subsequent timer expiry events
- CI integration: Add authentication failure test case to verify proper cleanup and UE state transition