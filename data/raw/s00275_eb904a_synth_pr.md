## Title: Fix integer overflow in nFAPI segment size configuration

### Summary
The nFAPI VNF and PNF P7 interface configurations used an excessively large default segment_size value (65000) that could cause integer overflow when calculating total buffer sizes. When segment_size is multiplied by max_num_segments (8), the result (520000) exceeds the range of uint16_t variables used in downstream buffer allocation logic, leading to truncated values and potential buffer overflows.

This change reduces the default segment_size from 65000 to 1400 bytes, which is a safer value that prevents overflow while still being efficient for typical network packets. The new value ensures that segment_size * max_num_segments (11200) comfortably fits within uint16_t range.

### Changes
- `nfapi/open-nFAPI/vnf/src/vnf_p7_interface.c`: Reduced `_public.segment_size` from 65000 to 1400 and updated comment to clarify overflow prevention
- `nfapi/open-nFAPI/pnf/src/pnf_p7_interface.c`: Applied the same segment_size reduction for consistency

### Implementation Details
The segment_size field is defined as uint32_t in the public interface, but downstream calculations involving total buffer size (segment_size * max_num_segments) were being stored in uint16_t variables, causing overflow. The value 1400 was chosen as it's a common MTU size that prevents overflow while maintaining good segmentation performance.

### Testing
- Verify that VNF/PNF initialization completes without overflow warnings
- Test with various message sizes to ensure segmentation still works correctly
- Run nFAPI integration tests to confirm no regression in functionality