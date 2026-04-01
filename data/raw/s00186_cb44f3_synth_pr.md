## Title: Replace magic numbers with symbolic constants in dlsch_procedures

### Summary
The `dlsch_procedures` function in the LTE eNB PHY scheduler used magic numbers `7` and `0` to represent beamforming modes when calling `get_G()`. These numeric literals lacked semantic meaning, making the code harder to understand and maintain. The value `7` corresponds to TM7 (Transmission Mode 7) beamforming, while `0` indicates no beamforming.

This change introduces symbolic constants `BEAMFORMING_MODE_TM7` and `BEAMFORMING_MODE_NONE` to replace these magic numbers, improving code readability and reducing the risk of errors when modifying beamforming logic. The constants are defined at the top of the file with clear comments indicating their purpose.

### Changes
- `openair1/SCHED/phy_procedures_lte_eNb.c`: 
  - Added symbolic constants `BEAMFORMING_MODE_TM7` (value 7) and `BEAMFORMING_MODE_NONE` (value 0) with descriptive comments
  - Replaced magic number `7` with `BEAMFORMING_MODE_TM7` and `0` with `BEAMFORMING_MODE_NONE` in the ternary expression within `dlsch_procedures` (line 340)

### Testing
- Verified successful compilation after the change
- Confirmed functional equivalence: the logic remains identical with same numeric values used
- Reviewed surrounding code to ensure no other instances of these magic numbers exist in the same context