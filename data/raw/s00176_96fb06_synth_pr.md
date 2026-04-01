## Title: Eliminate redundant PH calculation in UL MAC PDU header decoding

### Summary
Refactor the single-entry PHR (Power Headroom Report) calculation in `decode_ul_mac_sub_pdu_header` to eliminate redundant computation. The original code calculated `phr->PH - 32` in both branches of a conditional statement, which was inefficient and unnecessary. The new implementation computes the base value once and conditionally adds the secondary term only when needed, improving code clarity and reducing CPU cycles.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_ulsch.c`: Simplified the PH calculation logic by extracting the common `phr->PH - 32` computation outside the conditional. The code now uses a single base calculation followed by a conditional addition (`PH += phr->PH - 54`) when `phr->PH >= 55`, per 3GPP TS 38.133 Table 10.1.17.1-1.

### Implementation Details
The change reduces the number of arithmetic operations from 3 (two subtractions and one addition in the else branch) to 2 (one subtraction and potentially one addition) while maintaining identical functional behavior. This micro-optimization is particularly relevant since this function executes frequently during uplink scheduling.

### Testing
- Verified the refactored logic produces identical PH values for all possible `phr->PH` input ranges (0-63)
- Confirmed successful compilation of the `nr-softmodem` target
- Existing MAC scheduler test suite covers this code path and continues to pass