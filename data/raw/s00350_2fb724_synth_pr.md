## Title: Fix off-by-one array size error in PSBCH receiver

### Summary
The PSBCH receiver function `nr_rx_psbch()` was allocating three stack arrays with an incorrect size of `nb_re + 1` elements instead of `nb_re`. The variable `nb_re` represents the number of PSBCH data resource elements per OFDM symbol (`SL_NR_NUM_PSBCH_DATA_RE_IN_ONE_SYMBOL`). The receiver logic only accesses indices `0` through `nb_re - 1`, making the `+1` allocation unnecessary and wasteful. This off-by-one sizing could also lead to buffer boundary confusion and potential stack overflow issues in resource-constrained environments. This fix corrects the array dimensions to match the actual data size requirements, eliminating unused memory overhead while maintaining identical functional behavior.

### Changes
- `openair1/PHY/NR_UE_TRANSPORT/nr_psbch_rx.c`: 
  - Fixed array size for `rxdataF_ext` from `[nb_re + 1]` to `[nb_re]` (line 144)
  - Fixed array size for `dl_ch_estimates_ext` from `[nb_re + 1]` to `[nb_re]` (line 145)  
  - Fixed array size for `rxdataF_comp` from `[nb_re + 1]` to `[nb_re]` (line 169)

### Testing
- Verified code compiles without warnings or errors
- Confirmed all array access patterns remain within valid bounds `[0, nb_re-1]`
- No functional behavior changes expected as the extra element was never accessed in the original code