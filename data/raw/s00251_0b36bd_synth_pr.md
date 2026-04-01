## Title: Fix missed scheduling opportunity after CSI-RS processing

### Summary
UEs with pending data were not being scheduled downstream of CSI-RS processing because the scheduler was not being triggered after channel state information computation. The `nr_ue_csi_rs_procedures()` function computes critical channel state information (CQI, PMI, RI) that the MAC scheduler requires for making optimal scheduling decisions, but the scheduler invocation was missing in the processing pipeline.

This fix ensures that both downlink and uplink schedulers are triggered immediately after CSI-RS processing completes, allowing UEs with pending data to be properly scheduled using the freshly computed channel estimates.

### Changes
- **openair1/SCHED_NR_UE/phy_procedures_nr_ue.c**: 
  - Added includes for `NR_MAC_UE/mac_proto.h` and `NR_UE_PHY_INTERFACE/NR_IF_Module.h` to access scheduler functions
  - Added calls to `nr_ue_dl_scheduler()` and `nr_ue_ul_scheduler()` after `nr_ue_csi_rs_procedures()` completes
  - The scheduler calls are populated with current UE context (module_id, gNB_index, frame/slot numbers) to enable immediate scheduling decisions

### Implementation Details
The scheduler triggers are placed immediately after `ue->csirs_vars[gNB_id]->active = 0` to ensure they execute while the CSI-RS results are still hot in cache and the processing context is fully populated. Both DL and UL schedulers are invoked to handle asymmetric traffic patterns, using the same frame/slot context from the current processing procedure.

### Testing
- Verify scheduling occurs for UEs with pending DL/UL data after CSI-RS processing
- Confirm CQI/PMI/RI values computed during CSI-RS are correctly consumed by scheduler
- Run basic connectivity tests (registration, PDU session, traffic) to ensure no regression