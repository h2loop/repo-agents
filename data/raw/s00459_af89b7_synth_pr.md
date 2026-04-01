## Title: Fix HARQ process error by resetting timestamp in cache clear

### Summary
The `clear_cache()` function in the multi-RRU cleaning utility was not resetting the timestamp field when clearing cache entries. This caused stale timestamp data to persist across cache clear operations, which downstream HARQ processing logic could misinterpret as valid timing information. This led to incorrect redundancy version selection and retransmission errors, particularly in multi-RRU configurations where precise timing coordination is critical.

The fix ensures that both `tv_sec` and `tv_nsec` fields of the timestamp are explicitly zeroed when clearing cache entries, preventing any stale timing data from affecting HARQ process decisions.

### Changes
- `common/utils/T/tracer/hacks/multi-rru-clean.c`: Added timestamp field reset (`c[i].t.tv_sec = 0` and `c[i].t.tv_nsec = 0`) in the `clear_cache()` function to properly initialize all cache entry fields.

### Implementation Details
The change is minimal and surgical, adding only two assignment statements within the existing cache clearing loop. This ensures that when cache entries are reused, they start with a clean state and no residual timestamp data that could be misinterpreted by downstream HARQ retransmission logic. The fix maintains backward compatibility and has no performance impact.

### Testing
- Verified that cache entries are now fully reset, including timestamp fields
- Tested multi-RRU scenarios with HARQ retransmissions to confirm correct redundancy version selection
- Ran existing tracer and RRU integration tests to ensure no regression in functionality