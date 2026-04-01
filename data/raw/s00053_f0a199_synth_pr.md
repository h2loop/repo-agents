## Title: Add critical error logging for MBMS SI scheduling failures

### Summary
The MBMS SI scheduling functions silently fail when bcch_sdu_length is non-positive, indicating a failure to retrieve MBMS System Information data. The existing debug logs for these critical failure paths were commented out, making it extremely difficult to diagnose issues downstream of `schedule_SI_MBMS` and `schedule_SI`. Without proper error logging, operators and developers cannot detect or debug scenarios where MBMS SI data retrieval fails.

This change adds explicit error-level logging (LOG_E) to capture these failure scenarios with detailed diagnostic context. The new log statements include module ID, component carrier ID, frame/subframe numbers, and the invalid bcch_sdu_length value to enable rapid root cause analysis.

### Changes
- `openair2/LAYER2/MAC/eNB_scheduler_bch.c`: 
  - In `schedule_SI_MBMS()` (line ~916): Replaced commented-out LOG_D with active LOG_E reporting MBMS SI data retrieval failures
  - In `schedule_SI()` (line ~1247): Applied the same logging enhancement for consistency across both scheduling functions
  - Both locations now log: `[eNB %d] CCid %d Frame %d, subframe %d : Failed to get MBMS SI data (bcch_sdu_length %d)`

### Testing
- Verified successful compilation with the new log statements
- Confirmed log format adheres to OpenAirInterface MAC layer conventions
- No functional behavior changes; logging only enhancement