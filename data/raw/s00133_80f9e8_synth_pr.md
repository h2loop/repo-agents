## Title: Fix 64-QAM LLR computation chain in nr_phy_common

### Summary
The 64-QAM LLR (Log-Likelihood Ratio) computation function `nr_64qam_llr()` contained a copy-paste error that incorrectly calculated the sequential LLR values. The original code failed to properly chain the saturating subtraction operations, resulting in incorrect LLR outputs that would degrade channel decoding performance.

The bug manifested as a broken calculation chain: the second LLR value was computed directly from the raw received data instead of from the first LLR result, violating the expected 64-QAM demodulation logic. Additionally, the raw data pointer was dereferenced before increment, causing a subtle ordering bug.

The fix introduces a proper intermediate variable to cascade the operations correctly: raw data → first LLR (via ch_mag subtraction) → second LLR (via ch_magb subtraction from first LLR). This restores the correct mathematical relationship between the three LLR outputs required for 64-QAM demodulation as per 3GPP TS 38.211.

### Changes
- `openair1/PHY/nr_phy_common/src/nr_phy_common.c`: Fixed the LLR computation sequence in `nr_64qam_llr()` by adding intermediate variable `tmp1` and ensuring proper pointer increment order.

### Implementation Details
The corrected flow ensures:
1. Raw data is loaded and stored as the first LLR output
2. First saturating subtraction computes `tmp1 = ch_mag - data`
3. Second saturating subtraction computes `ch_magb - tmp1` (not `ch_magb - data`)

This maintains the proper dependency chain for 64-QAM's three-bit soft decision outputs.

### Testing
- Verified LLR calculation logic against 3GPP 38.211 specifications
- Ran PHY layer unit tests for 64-QAM modulation/demodulation
- Confirmed no regressions in downlink throughput tests