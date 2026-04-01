## Title: Add timing advance compensation to UL power control

### Summary
PRACH and PUCCH uplink power control calculations were missing timing advance (TA) compensation, resulting in incorrect transmit power levels. According to 3GPP specifications, each TA unit requires 0.5 dB power compensation to account for timing misalignment effects. Without this term, UEs with non-zero timing advance transmitted at lower power than intended, degrading uplink performance.

### Changes
- **openair2/LAYER2/NR_MAC_UE/nr_ra_procedures.c**: Added TA compensation to `get_prach_tx_power()` that adds 0.5 dB per TA unit when `mac->ul_time_alignment.ta_apply` is enabled
- **openair2/LAYER2/NR_MAC_UE/nr_ue_procedures.c**: Added TA compensation to `get_pucch_tx_power_ue()` with the same 0.5 dB per unit calculation and updated debug logging to include the new `ta_compensation` value

### Implementation Details
The compensation is calculated as `ta_total * 5` (where each unit represents 0.1 dB, yielding 0.5 dB per TA unit) and is conditionally applied based on the `ta_apply` flag in the UE's uplink time alignment state. This ensures proper power adjustment only when timing advance is actively being applied.