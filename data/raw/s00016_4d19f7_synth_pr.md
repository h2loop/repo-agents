## Title: Fix scheduling priority inversion for SI and PAGING traffic

### Summary
Fixes a scheduling priority inversion in the eNB downlink scheduler where regular UE traffic was being prioritized over System Information (SI) and PAGING traffic. According to 3GPP specifications, SI and PAGING should have the highest scheduling priority, but the fair round-robin scheduler was processing them in the wrong order, causing potential delays for critical system broadcasts.

The fix explicitly inserts SI and PAGING traffic into the UE selection list with appropriate priority levels before processing regular UE traffic. SI is assigned the highest priority (`SCH_DL_SI`) followed by PAGING, ensuring proper 3GPP-compliant scheduling order.

### Changes
- `openair2/LAYER2/MAC/eNB_scheduler_fairRR.c`: Added priority-aware scheduling logic in `dlsch_scheduler_pre_ue_select_fairRR()` to check for active SI and PAGING traffic and insert them into the scheduler's UE selection list with highest priority before regular UE processing. SI uses special UE ID -1 and PAGING uses -2 to distinguish them from regular UEs.

### Implementation Details
- SI traffic is scheduled first when `SI_active == 1`, using aggregation level 4 for reliability and RNTI value `SI_RNTI`
- PAGING traffic is scheduled next when `PAGING_active == 1`, also using aggregation level 4 and RNTI value `P_RNTI`
- Both traffic types bypass the standard UE selection loop and are directly inserted into `dlsch_ue_select[CC_id].list` with priority values that ensure they are processed first
- The solution maintains backward compatibility and only activates when the respective `SI_active` or `PAGING_active` flags are set