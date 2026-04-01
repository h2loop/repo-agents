## Title: Fix missing DRB configuration in UE context modification for handover

### Summary
The UE context modification request during handover was not properly configuring Data Radio Bearers (DRBs), only Signaling Radio Bearers (SRBs). This caused the target DU to lack essential bearer information including RLC mode, tunnel endpoints, QoS parameters, and network slice information after handover, leading to potential service interruption or handover failure.

The fix adds comprehensive DRB configuration to `rrc_deliver_ue_ctxt_modif_req()` by iterating through established DRBs and populating all required fields for the F1AP context modification message. Each active DRB is configured with its PDU session association, QoS flow parameters, tunnel information (TEID, IP address, port), and NSSAI for network slicing support.

### Changes
- `openair2/RRC/NR/rrc_gNB_mobility.c`: Added DRB configuration logic in `rrc_deliver_ue_ctxt_modif_req()` to properly populate `f1ap_ue_context_modif_req_t` with established DRBs, their RLC modes, tunnel endpoints, QoS parameters, and NSSAI from associated PDU sessions.

### Implementation Details
- Iterates through up to 32 DRBs, skipping inactive ones
- Supports both UM and AM RLC modes based on RRC configuration
- Configures uplink tunnel parameters with CU-UP address and TEID
- Associates each DRB with its PDU session to extract QoS characteristics and NSSAI
- Validates single QoS flow per DRB as per current implementation constraints
- Maintains existing SRB configuration (SRB1 and SRB2)