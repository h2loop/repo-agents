## Title: Add empty_value parameter to throughput logger for 3GPP compliance

### Summary
The throughput logger was missing a configurable empty value parameter, which is conditionally mandatory per 3GPP specifications for certain measurement reporting scenarios. The logger previously hardcoded zero when resetting buffer slots during tick events, but specifications require the ability to distinguish between "no data" and "zero throughput" conditions. This patch adds an `empty_value` parameter to `new_throughputlog()`, allowing callers to specify a custom placeholder value (e.g., NaN or -1) for empty buffer slots.

### Changes
- `common/utils/T/tracer/logger/throughputlog.c`: Added `empty_value` field to `throughputlog` struct; modified `_tick_event()` to use `empty_value` instead of hardcoded zero; updated `new_throughputlog()` signature
- `common/utils/T/tracer/logger/logger.h`: Updated `new_throughputlog()` function declaration to include `float empty_value` parameter
- `common/utils/T/tracer/enb.c`: Updated two calls to `new_throughputlog()` to pass `0.0f` for backward compatibility

### Implementation Details
This change mirrors the existing `ticked_ttilog` implementation which already supports configurable empty values. The parameter is stored in the logger instance and applied when resetting the circular buffer during tick events, enabling proper distinction between valid zero measurements and empty slots in time-series throughput data.