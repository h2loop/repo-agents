## Title: Fix NULL pointer dereference in RA response window configuration

### Summary
The UE MAC layer function `nr_get_RA_window()` dereferences `rach_ConfigCommon` without null checking, causing crashes when the configuration is unavailable during early RA procedure initialization. This leads to NGAP interface handling failures downstream when the RA response window cannot be properly configured.

This change adds defensive NULL validation for `mac->current_UL_BWP.rach_ConfigCommon` before accessing its members. When NULL, the function logs a warning and sets a safe default RA window count of 10 slots, allowing the RA procedure to continue gracefully without crashing.

### Changes
- `openair2/LAYER2/NR_MAC_UE/nr_ra_procedures.c`: Added NULL pointer check at entry of `nr_get_RA_window()`. If `rach_ConfigCommon` is NULL, logs warning and sets `ra->RA_window_cnt = 10` (sl10 per 3GPP spec) before early return, preventing segmentation faults.

### Implementation Details
The default value of 10 slots aligns with 3GPP TS 38.321 RA response window specifications. This conservative approach ensures UE can proceed with random access during transient configuration states, improving robustness during initial attach and handover scenarios where configuration may not be immediately available.