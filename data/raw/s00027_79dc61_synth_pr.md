## Title: Fix PUCCH format 3/4 channel coding index construction

### Summary
The `generate_pucch3x()` function incorrectly constructs the channel coding table index from payload bits using arithmetic addition instead of bitwise OR, causing incorrect index values. Payload bits are also not masked, potentially using non-binary values. Additionally, an uninitialized variable in the scrambling logic leads to undefined behavior. These bugs affect PUCCH format 3/4 encoding for uplink control information.

This patch corrects the index construction to use proper bitwise operations with masking, and initializes the scrambling variable, ensuring correct PUCCH encoding and deterministic behavior.

### Changes
- `openair1/PHY/LTE_UE_TRANSPORT/pucch_ue.c`:
  - Fixed channel coding index calculation: Changed `chcod_tbl_idx += (payload[i]<<i)` to `chcod_tbl_idx |= ((payload[i] & 1) << i)` to correctly build bitwise index
  - Initialized scrambling variable: Set `uint32_t x1 = 0` to prevent undefined behavior in scrambling sequence generation

### Implementation Details
The channel coding table index is built from 7 payload bits, where each bit should contribute exactly one bit to the index. The original `+=` operator caused arithmetic accumulation rather than bitwise composition. The added `& 1` mask ensures payload values are treated as binary bits. The `x1` initialization fixes a latent undefined behavior issue in the scrambling sequence generation used for PUCCH data scrambling.

### Testing
- Verified correct encoding with PUCCH format 3/4 test patterns
- Confirmed deterministic scrambling behavior
- Tested with NR UE softmodem to ensure no functional regression in uplink control channel transmission