## Title: Fix measurement configuration deadlock with dedicated mutex

### Summary
The NR RRC measurement configuration code had a race condition leading to potential deadlock due to unsynchronized access to the shared `measurementConfiguration` structure. This introduces a dedicated mutex to protect all accesses to measurement configuration data, ensuring thread-safe operation during A2/A3 event preparation and periodic reporting.

### Changes
- `openair2/RRC/NR/nr_rrc_defs.h`: Added `pthread_mutex_t measurement_mutex` field to `gNB_RRC_INST_s` struct to protect `measurementConfiguration`
- `openair2/GNB_APP/gnb_config.c`: Initialize measurement mutex in `RCconfig_NRRRC()` during RRC instance allocation
- `openair2/RRC/NR/rrc_gNB.c`: Wrap measurement config access in `nr_rrc_get_measconfig()` with mutex lock/unlock calls

### Implementation Details
- Mutex is held across the entire measurement preparation sequence: parameter access, event report preparation (`prepare_a2_event_report()`, `prepare_periodic_event_report()`), and final `get_MeasConfig()` call
- Proper unlock on both success and error paths prevents mutex leakage
- Mutex lifecycle matches the RRC instance lifecycle, initialized once at creation

### Testing
- Verified deadlock resolution under concurrent measurement configuration requests
- Confirmed correct mutex behavior in both `du->mtc` present and absent code paths
- Ensured no regression in handover procedures dependent on measurement reports