## Title: Fix MCS selection in MBMS to consider channel quality and UE capability

### Summary
The MBMS PMCH configuration previously used a static MCS value from M2AP scheduling information without considering actual channel quality or UE receiver capabilities. This could result in excessive block error rates when channel conditions were poor, or suboptimal throughput when UEs supported higher-order modulation. The fix introduces dynamic MCS selection that adapts to real-time channel conditions and UE capabilities.

### Changes
- `openair2/RRC/LTE/rrc_eNB_M2AP.c`: 
  - Added `get_ue_max_mcs_capability()` helper function to estimate maximum MCS based on UE category (conservatively assumes Category 2 capabilities for MBMS, limiting to MCS 21/16QAM)
  - Modified MCS selection logic in `rrc_M2AP_do_MBSFNAreaConfig()` to:
    - Calculate average CQI across all active UEs
    - Map CQI to MCS using the standard CQI-to-MCS mapping table
    - Select the most conservative value among: configured MCS, CQI-derived MCS, and UE capability-limited MCS
    - Log the final MCS selection for debugging

### Implementation Details
The new MCS selection algorithm prioritizes reliability for broadcast services by:
1. Averaging DL CQI values from the MAC layer across all active UEs
2. Using the standard 3GPP CQI-to-MCS mapping table
3. Applying a conservative cap based on typical UE Category 2 capabilities (MCS 21) for MBMS
4. Selecting `min(configured_mcs, cqi_based_mcs, ue_capability_mcs)` to ensure robust transmission

### Testing Recommendations
- Verify MCS selection under varying CQI conditions (poor, moderate, excellent)
- Test with different UE categories to ensure capability limits are respected
- Confirm MBMS service continuity and BLER performance improvements