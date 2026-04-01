## Title: Fix incomplete MAC configuration in MBMS SIB13 setup

### Summary
The `rrc_M2AP_do_SIB23_SIB13` function was violating 3GPP signaling procedure sequence by sending an incompletely populated MAC configuration request to the lower layers. The `rrc_mac_config_req_eNB_t` structure was missing critical MBMS parameters including the MBSFN subframe configuration list, RNTI assignment, and FeMBMS flag. This caused the MAC layer to receive incomplete configuration during MBMS cell setup, potentially leading to subframe allocation failures and non-compliant MBMS operation.

The fix ensures all required parameters are properly populated before invoking the MAC configuration, maintaining the correct signaling flow between RRC and MAC layers as per 3GPP specifications for MBMS cell configuration.

### Changes
- `openair2/RRC/LTE/rrc_eNB_M2AP.c`: 
  - Moved `carrier->MBMS_flag = 1;` earlier to ensure proper state before configuration
  - Enhanced `rrc_mac_config_req_eNB_t tmp` initialization with:
    - `tmp.rnti = 0xfffd;` (MBMS RNTI assignment)
    - `tmp.mbsfn_SubframeConfigList = carrier->sib2->mbsfn_SubframeConfigList;` (MBSFN subframe configuration)
    - `tmp.FeMBMS_Flag = carrier->FeMBMS_flag;` (FeMBMS capability flag)
  - Fixed module ID parameter from `ctxt_pP->module_id` to `Mod_id` for consistency with function signature

### Implementation Details
The changes ensure the MAC layer receives complete MBMS configuration atomically, preventing race conditions and maintaining proper state synchronization between RRC and MAC during cell setup. The `0xfffd` RNTI value is the standard MBMS RNTI defined in 3GPP specifications.