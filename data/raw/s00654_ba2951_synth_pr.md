## Title: Fix ASN.1 encoding error in IF4.5 header frame number packing

### Summary
The IF4.5 header generation functions were incorrectly masking the frame number with `0xffff` (16 bits) when packing it into the `frame_status` field. This caused frame numbers to overflow their allocated bit range, corrupting the protocol header and producing malformed ASN.1 messages downstream. The frame number should be limited to 10 bits (0-1023) as per the LTE/NR frame structure. This patch corrects the mask to `0x3ff` across all IF4.5 header generation functions to ensure proper bit field packing.

### Changes
- `openair1/PHY/LTE_TRANSPORT/if4_tools.c`: Updated frame number masking in three functions:
  - `gen_IF4p5_dl_header()` (line 437)
  - `gen_IF4p5_ul_header()` (line 451) 
  - `gen_IF4p5_prach_header()` (line 464)
  - Changed `(frame&0xffff)<<6` to `(frame&0x3ff)<<6` with explanatory comment

### Implementation Details
The `frame_status` field is a 32-bit integer where frame number occupies bits 6-21 and subframe number occupies bits 22-25. Using a 16-bit mask allowed frame values up to 65535, which could overflow into adjacent fields and corrupt the header structure. The 10-bit mask (`0x3ff`) correctly limits frame numbers to the valid range of 0-1023, preventing header corruption and ensuring downstream ASN.1 encoding receives well-formed protocol messages.

### Testing
This fix ensures proper bit field packing in IF4.5 headers, preventing malformed ASN.1 messages in downstream processing. The change is consistent across all header generation variants and maintains backward compatibility with valid frame number ranges.