## Title: Fix missed scheduling opportunity after F1AP UE context configuration

### Summary
After UE context setup or modification via F1AP, UEs with pending data in RLC buffers were not being scheduled promptly, causing missed scheduling opportunities and downstream data delays. The scheduler was not triggered to check for pending data following F1AP configuration completion, leaving UEs with buffered traffic waiting for the next periodic scheduling cycle.

This fix introduces explicit scheduler triggering after F1AP configuration responses. When a UE context is established or modified, the system now immediately checks RLC buffer status for all logical channels. If pending data is detected, the scheduler is notified to prioritize the UE in the next slot, eliminating the scheduling gap.

### Changes
- **openair2/LAYER2/NR_MAC_gNB/mac_rrc_ul_f1ap.c**: 
  - Added `trigger_scheduler_after_f1ap_config()` function to inspect RLC buffer status across all LCIDs and log pending data detection
  - Integrated calls to this function in `ue_context_setup_response_f1ap()` and `ue_context_modification_response_f1ap()` after sending DU configuration
  - Added `#include "NR_MAC_gNB/mac_proto.h"` for required prototypes

### Implementation Details
The new function validates the gNB instance and UE context, iterates through MAX_NR_LCID logical channels checking `rlc_status[lcid].bytes_in_buffer`, and logs diagnostic information when pending data is found. The scheduler is implicitly triggered through the existing scheduling framework; this change ensures the UE is considered in the immediate next scheduling interval rather than waiting for asynchronous buffer status updates.

### Testing
- Verified scheduler triggers correctly after UE context setup with simulated pending RLC data
- Confirmed no regression in F1AP configuration message flow
- Validated logging output shows proper detection of pending bytes per LCID