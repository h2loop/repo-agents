## Title: Fix integer underflow in bandwidth formatting utility

### Summary
The `bps()` function in the tracer utility library calculates a logarithmic index (`flog`) to select appropriate bandwidth units (b/s, kb/s, Mb/s, Gb/s). When formatting values less than 1, the calculation `floor(floor(log10(v)) / 3)` produces negative results, causing negative array indexing into the `bps_unit` array. This leads to undefined behavior and potential memory corruption when processing very low or zero throughput measurements.

This fix adds a defensive bounds check to clamp the index to 0 when negative, ensuring valid array access for all input values. The change prevents crashes and garbled output in low-traffic scenarios while maintaining correct formatting for normal bandwidth ranges.

### Changes
- `common/utils/T/tracer/utils.c`: Added `if (flog < 0) flog = 0;` after the unit index calculation to prevent negative array indexing. This ensures the function gracefully handles edge cases where `v < 1`.

### Testing
- Verified correct behavior for edge case values (0, 0.1, 0.5, 0.9) that previously triggered underflow
- Confirmed normal operation for typical bandwidth values (100, 1000, 1000000) remains unchanged
- Validated output formatting in `scrolltti.c` and `xy_plot.c` calling contexts with simulated low-throughput scenarios
- Ensured no regression in tracer GUI display functionality