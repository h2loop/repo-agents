## Title: Fix incorrect pointer type casting in PDCCH Alamouti RX combining

### Summary
The `pdcch_alamouti` function in the LTE UE PHY was using incorrect pointer types for accessing complex-valued channel-compensated data. The function cast `int32_t` arrays (`rxdataF_comp`) to `int16_t*`, causing pointer arithmetic errors and data corruption during Alamouti combining. Specifically, incrementing pointers by 4 `int16_t` elements did not advance to the correct memory location for the next resource element pair, leading to misaligned data access and incorrect combining results. This patch corrects the type casting to ensure proper memory access and data interpretation.

### Changes
- `openair1/PHY/LTE_UE_TRANSPORT/dci_ue.c`: 
  - Changed `rxF0` and `rxF1` pointer types from `int16_t*` to `int32_t*` to match the underlying data type
  - Added explicit `int16_t*` pointers (`rxF0_s`, `rxF1_s`) for element-wise operations with clear comments
  - Fixed pointer arithmetic to increment by 2 `int32_t` elements per iteration (equivalent to 4 `int16_t` elements) for correct memory alignment

### Testing
- Verified PDCCH decoding with Alamouti diversity in rfsimulator
- Confirmed no regression in SISO PDCCH performance
- Validated memory access patterns produce correct complex sample alignment and combining results