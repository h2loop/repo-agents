## Title: Fix signed/unsigned comparison mismatch in ESM Information Transfer Flag decoder

### Summary
The `decode_u8_esm_information_transfer_flag` function in the NAS layer contained a signed/unsigned integer comparison mismatch that could lead to incorrect branching behavior. The function declared a signed `int decoded` variable that was compared against an unsigned `uint32_t len` parameter within the `CHECK_PDU_POINTER_AND_LENGTH_DECODER` macro. This mismatch caused potential buffer underrun checks to fail incorrectly, leading to malformed NAS message handling and compiler warnings about signed/unsigned comparisons.

The fix adds an explicit unsigned length check before invoking the TLV decoder macro, ensuring both comparison operands are unsigned. This prevents incorrect branching when `len` has large values and eliminates the signed/unsigned comparison warning.

### Changes
- `openair3/NAS/COMMON/IES/EsmInformationTransferFlag.c`: Added manual length validation using explicit unsigned comparison `(len < (uint32_t)ESM_INFORMATION_TRANSFER_FLAG_MINIMUM_LENGTH)` before the TLV decoder macro. This ensures proper unsigned comparison semantics and correct error handling for buffer length validation.

### Implementation Details
The fix performs the length check manually with both operands cast to `uint32_t`, returning `TLV_DECODE_BUFFER_TOO_SHORT` immediately if the buffer is too small. This avoids the signed/unsigned mismatch while preserving the original error handling logic. The subsequent `CHECK_PDU_POINTER_AND_LENGTH_DECODER` macro call remains for additional validation consistency with other NAS decoder functions.

### Testing
- Verified the fix resolves the signed/unsigned comparison compiler warning
- Confirmed correct NAS message decoding behavior for both valid and invalid length scenarios
- Ensured no regression in existing NAS message processing pipelines