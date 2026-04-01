## Title: Fix missing tb_scaling initialization in NR Msg2 generation

### Summary
The `nr_generate_Msg2` function in the gNB Random Access Response (RAR) generation code was not explicitly setting the `tb_scaling` parameter for PDSCH PDU configuration. This omission could lead to undefined behavior or incorrect transport block size calculations for Msg2 transmissions. According to 3GPP TS 38.214, Msg2 transmissions must use `tb_scaling = 0` (representing 100% scaling, i.e., no scaling applied). This patch ensures compliance with the specification by explicitly initializing the parameter.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/gNB_scheduler_RA.c`: Added explicit `tb_scaling = 0` assignment in `nr_generate_Msg2` before PDSCH PDU population, with a comment referencing the 3GPP specification.

### Implementation Details
The fix is placed immediately after the TBS and LBRM calculations and before LDPC base graph selection, ensuring the scaling factor is properly set in the PDU structure. The value 0 corresponds to 100% scaling (no reduction) as defined in the 3GPP standard for RAR messages, which use fixed MCS and no TB size scaling.