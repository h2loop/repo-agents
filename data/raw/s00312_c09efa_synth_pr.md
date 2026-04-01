## Title: Fix uninitialized memory read in Polar decoder path metric update

### Summary
The Polar decoder's `updatePathMetric2` function was reading uninitialized memory when processing information bits. The function accesses LLR values for newly created decoder paths (indices `currentListSize` to `2*listSize-1`) before they were initialized, leading to undefined behavior that could cause incorrect decoding results or crashes.

The root cause was the order of operations in the information bit processing branch: `updatePathMetric2` was called immediately after path splitting, but the LLR values for the new paths were only copied afterward. This meant the path metric update operated on uninitialized memory.

The fix reorders the operations to first copy LLR values from existing paths to the newly created paths, ensuring all memory is properly initialized before `updatePathMetric2` reads from it. This eliminates the undefined behavior while preserving the original algorithm logic.

### Changes
- `openair1/PHY/CODING/nrPolar_tools/nr_polar_decoder.c`: Moved the LLR initialization loop before the `updatePathMetric2` call in the information bit processing branch. Added clarifying comments to document the initialization requirement.

### Testing
- Verified with Valgrind that no uninitialized memory reads occur during Polar decoding
- Ran existing Polar decoder unit tests to confirm correct decoding behavior
- Tested with various code block sizes and list sizes to ensure no regression
- Checked that path metrics are now computed from valid initialized data