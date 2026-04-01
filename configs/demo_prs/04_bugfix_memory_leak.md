## Title: Fix memory leak in LDPC decoder on early return paths

### Summary
The NR LDPC decoder allocated temporary `mbuf` structures at the beginning of the decoding pipeline for storing intermediate lifting results and parity check data. Several early return paths -- triggered by unsupported lifting size, invalid base graph selection, or max iteration count exceeded -- exited the function without freeing these buffers. Over sustained operation with occasional decode failures (common at low SNR), this led to a steady memory leak that could eventually exhaust system memory on long-running gNB deployments.

This fix restructures the LDPC decoder to use a single cleanup label at the end of the function. All early return paths now jump to this label via `goto`, ensuring that allocated mbufs are always freed regardless of the exit reason. The function return code is set before the jump so callers still receive the correct error status.

### Changes
- `openair1/PHY/CODING/nrLDPC_decoder/nrLDPC_decoder.c`: Replaced three direct `return` statements in error paths with `goto cleanup`. Added `cleanup:` label at end of `nrLDPC_decoder()` that frees `p_procBuf->cnProcBuf`, `p_procBuf->bnProcBuf`, and `p_procBuf->llrProcBuf` if non-NULL before returning.
- `openair1/PHY/CODING/nrLDPC_defs.h`: Added `is_allocated` flag to `t_nrLDPC_procBuf` to allow safe conditional free in the cleanup path without double-free risk.
- `openair1/PHY/CODING/nrLDPC_init.h`: Set `is_allocated` flag to true after successful buffer allocation in `nrLDPC_init_mem()`.

### Testing
- Ran `nr-dlsim` at SNR=0dB for 10,000 frames to trigger frequent LDPC decode failures. Monitored RSS with Valgrind Massif; confirmed memory usage is now stable rather than growing linearly.
- Ran Valgrind memcheck on `nr-dlsim` short run: zero "definitely lost" bytes reported in the LDPC decoder (previously 14MB over 1,000 frames).
- No throughput or latency regression observed in the `nr-phy-sim` CI suite.
