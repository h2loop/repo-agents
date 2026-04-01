## Title: Fix incorrect frequency band list population in F1AP configuration update

### Summary
The F1AP DU interface management code incorrectly populated the `supportedSULBandList` instead of `freqBandListNr` when constructing the DL NRFreqInfo structure in `DU_send_gNB_DU_CONFIGURATION_UPDATE`. This caused the DU to send malformed configuration updates to the CU, containing resource block allocation parameters in the wrong ASN.1 container. The CU would then parse incorrect frequency band information, leading to scheduling constraint violations and potential resource allocation failures.

This fix corrects the target list for `dl_freqBandNrItem` to use `fDD_Info->dL_NRFreqInfo.freqBandListNr.list` and properly allocates `dl_supportedSULFreqBandItem` on the heap using `asn1cSequenceAdd` instead of as a stack variable, ensuring correct ASN.1 structure encoding.

### Changes
- `openair2/F1AP/f1ap_du_interface_management.c`: Fixed the destination list in `asn1cSequenceAdd` for `dl_freqBandNrItem` and corrected `dl_supportedSULFreqBandItem` allocation from stack to heap with proper pointer assignment.

### Testing
- Verified F1AP configuration update message encoding completes without errors
- Confirmed correct ASN.1 structure layout through message inspection
- Basic connectivity test with CU-DU interface shows proper configuration exchange without scheduling errors