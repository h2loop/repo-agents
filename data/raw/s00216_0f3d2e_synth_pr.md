## Title: Fix deadlock in M2AP message handling by removing duplicate responses

### Summary
Fix a deadlock caused by inconsistent lock acquisition ordering in M2AP message processing. The ENB_APP layer was sending duplicate responses for MBMS session control messages that are already handled by the RRC layer. Since RRC holds `cell_info_mutex` while processing these messages and sending its own responses, the duplicate responses from ENB_APP created a race condition leading to deadlock. This patch removes the redundant response generation from ENB_APP, allowing RRC to remain the sole authority for M2AP response messages.

### Changes
- **openair2/ENB_APP/enb_app.c**: 
  - Modified `eNB_app_handle_m2ap_mbms_session_start_req()` to remove ITTI message allocation and sending of `M2AP_MBMS_SESSION_START_RESP`
  - Modified `eNB_app_handle_m2ap_mbms_scheduling_information()` to remove ITTI message allocation and sending of `M2AP_MBMS_SCHEDULING_INFORMATION_RESP`
  - Both functions now log that messages are forwarded to RRC and return immediately
  - Added detailed comments explaining the deadlock scenario and why ENB_APP must not send duplicate responses

### Implementation Details
The root cause was dual response paths: RRC processes M2AP requests while holding `cell_info_mutex`, then sends appropriate responses via ITTI. ENB_APP was independently sending identical responses, creating potential lock ordering conflicts. The fix eliminates the ENB_APP response path entirely, making RRC the single source of truth for M2AP responses. Logging statements replace the removed functionality to maintain observability.

### Testing
- Verified MBMS session start/stop procedures complete without deadlock
- Confirmed RRC layer continues to send proper M2AP responses after processing
- Tested with multiple concurrent MBMS sessions to ensure no regression in scalability