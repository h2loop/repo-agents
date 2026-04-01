## Title: Fix buffer overflow vulnerability in S1AP UE Context Release Request

### Summary
The S1AP protocol specifies that eNB UE S1AP ID is a 24-bit integer per 3GPP standards. The function `rrc_eNB_send_S1AP_UE_CONTEXT_RELEASE_REQ` was directly assigning the eNB_ue_s1ap_id from the UE context to the S1AP message without validation. If the ID exceeded 24 bits, this could cause a buffer overflow in downstream S1AP encoding functions when the message is serialized for transmission over the S1 interface.

This patch adds bounds checking to ensure the eNB_ue_s1ap_id value fits within the 24-bit limit before assignment. When an invalid ID is detected, it logs an error message and caps the value at 0xFFFFFF to prevent the overflow while allowing the procedure to continue gracefully.

### Changes
- `openair2/RRC/LTE/rrc_eNB_S1AP.c`: Added validation logic in `rrc_eNB_send_S1AP_UE_CONTEXT_RELEASE_REQ()` to check if `ue_context_pP->ue_context.eNB_ue_s1ap_id` exceeds 0xFFFFFF (24-bit maximum). If it does, log an error and cap the value; otherwise, use the original value. This prevents potential buffer overflows in downstream S1AP message encoding.

### Testing
- Code review confirms the 24-bit limit aligns with S1AP protocol specifications
- The error logging will help identify any root causes generating invalid IDs in the system
- The graceful truncation ensures the UE context release procedure completes even when ID validation fails