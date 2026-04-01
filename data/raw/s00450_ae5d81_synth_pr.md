## Title: Fix incorrect physical cell ID extraction in X2AP EN-DC SgNB Addition Request

### Summary
Correct the source of the target physical cell ID when building X2AP ENDC SgNB Addition Request messages during EN-DC procedures. The code was incorrectly reading `physCellId` from LTE neighbor cell measurements (`measResultListEUTRA`) instead of NR neighbor cell measurements (`measResultNeighCellListNR_r15`). Additionally, a hardcoded zero assignment was overwriting the field after it was set. This caused the SgNB Addition Request to contain invalid or zero target cell identity, leading to X2AP procedure failures.

### Changes
- `openair2/RRC/LTE/rrc_eNB.c`: 
  - Changed `target_physCellId` assignment to use `measResultNeighCellListNR_r15.list.array[0]->pci_r15` instead of `measResultListEUTRA.list.array[0]->physCellId`
  - Removed the erroneous `target_physCellId = 0` hardcoded assignment
  - Cleaned up commented-out code

### Implementation Details
The fix ensures that during measurement report processing for EN-DC, the NR secondary cell group's physical cell ID is correctly extracted from the NR neighbor cell list structure (`MeasResultNeighCellListNR-r15`) rather than the LTE neighbor list. This aligns with 3GPP TS 36.331 and TS 38.331 specifications for ENDC SgNB Addition procedures.