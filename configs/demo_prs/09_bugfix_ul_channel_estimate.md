## Title: Fix UL channel estimate mapping in 2-layer MMSE receiver

### Summary
The gNB uplink channel estimation module contained an incorrect antenna port mapping when computing the channel matrix for the 2-layer MMSE-IRC receiver. Specifically, the DMRS-based channel estimates for antenna port 1001 (second DMRS port in the 2-layer case) were being mapped to the wrong row of the channel matrix `H[rx_ant][layer]`. The second layer's estimates were copied into the first layer's slot for receive antenna index 1, effectively duplicating layer 0 estimates and discarding layer 1 information.

This caused the MMSE equalizer to produce a near-singular matrix inversion for rank-2 transmissions, leading to severely degraded UL throughput in 2x2 MIMO configurations (measured 40-50% below expected). Single-layer transmissions were unaffected because only antenna port 1000 was used. The fix corrects the index mapping so that `H[rx_ant][layer]` is populated with the channel estimate from the correct DMRS port for each layer.

### Changes
- `openair1/PHY/NR_ESTIMATION/nr_ul_channel_estimation.c`: Fixed the loop in `nr_pusch_channel_estimation()` that maps DMRS port indices to channel matrix layer indices. Changed `chEst[ant][p - start_port]` indexing to correctly use the DMRS port offset relative to the configured starting port, rather than the absolute port number.
- `openair1/PHY/NR_ESTIMATION/nr_ul_estimation.h`: Added a clarifying comment documenting the antenna port to layer mapping convention used by the channel estimation output buffer.

### Testing
- Ran `nr-ulsim` with 2x2 MIMO, rank 2, MCS 20 at SNR 20dB: UL throughput recovered from 28 Mbps to the expected 52 Mbps (20 MHz bandwidth).
- Ran the `nr-sa-2x2-mimo` CI pipeline with iperf UL traffic; measured throughput matches theoretical expectations within 5%.
- Verified no regression in 1-layer (SISO and rank-1 MIMO) configurations using `nr-ulsim` sweeps.
