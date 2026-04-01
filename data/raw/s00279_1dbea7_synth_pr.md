## Title: Fix scheduling priority inversion in nfapi_vnf_phy_info_list

### Summary
The `nfapi_vnf_phy_info_list_add` function was inserting new PHY info entries at the head of the linked list (LIFO order). Since `nfapi_vnf_phy_info_list_find` traverses from head to tail, this caused a scheduling priority inversion where recently added entries would be served before older ones, regardless of their intended priority. In practice, this meant lower-priority traffic could preempt higher-priority traffic.

This fix changes the insertion behavior to append new entries at the tail (FIFO order), preserving the intended priority sequence. The new implementation properly handles the empty list case and maintains the `next` pointer initialization.

### Changes
- `nfapi/open-nFAPI/vnf/src/vnf.c`: Modified `nfapi_vnf_phy_info_list_add()` to traverse to the list tail before inserting new entries. Added explicit NULL initialization for `info->next` and proper handling when `config->phy_list` is empty.

### Testing
- Verified PHY info entries are now retrieved in FIFO order through `nfapi_vnf_phy_info_list_find`
- Confirmed no memory leaks or regressions in list operations
- Validated that priority inversion scenarios no longer occur in VNF scheduling