## Title: Add protocol timer for TX data request latency measurement

### Summary
The FAPI VNF layer lacked protocol timer instrumentation in the TX data request path, preventing measurement of round-trip latency for downlink data transmissions. The `oai_fapi_tx_data_req()` function would send messages without capturing timing information, making it impossible to monitor performance or detect latency regressions in the FAPI interface.

This change adds start/stop timer calls around the message transmission to measure per-request latency and maintain a running average. The timer records a high-resolution timestamp before sending the TX data request, then captures a second timestamp upon successful completion. The delta is stored in a circular buffer of the last 8 samples, with a running average computed to smooth transient variations.

### Changes
- `nfapi/oai_integration/aerial/fapi_nvIPC.c`: Added timer start logic before `send_p7_msg()` that records `previous_t1`. Added timer stop logic after successful transmission that records `previous_t2`, calculates latency, stores it in an 8-element circular buffer indexed by `sequence_number`, and updates the running `average_latency`.

### Implementation Details
- Uses `vnf_get_current_time_hr()` for microsecond-precision timing
- Latency measurement only occurs on successful sends (`retval == 0`)
- Circular buffer size of 8 provides recent history while limiting memory overhead
- Running average uses weighted formula: `(average * 7 + new_sample) / 8` for smooth tracking
- Timer state is maintained per-connection in the `p7_connections` structure