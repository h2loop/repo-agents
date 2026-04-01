## Title: Fix buffer overflow in PNF config request handlers

### Summary
The PNF (Physical Network Function) configuration request handlers contain loops that iterate over `req.pnf_phy_rf_config.number_phy_rf_config_info` without validating against the maximum allowed PHY-RF instances (`NFAPI_MAX_PHY_RF_INSTANCES`). When a malformed or misconfigured request specifies a count exceeding this limit, the code iterates beyond array boundaries, causing potential buffer overflows, memory corruption, and undefined behavior.

This patch adds proper bounds checking to both legacy and NR PNF config request handlers, ensuring loops terminate at the configured maximum regardless of the requested count. The fix prevents crashes and security vulnerabilities while maintaining compatibility with valid configurations.

### Changes
- `nfapi/open-nFAPI/pnf/src/pnf.c`: Modified two loop conditions in `pnf_handle_pnf_config_request()` (line 208) and `pnf_nr_handle_pnf_config_request()` (line 275) to include `&& i < NFAPI_MAX_PHY_RF_INSTANCES` bounds check

### Implementation Details
The loops allocate and configure PHY-RF instances based on the request's `number_phy_rf_config_info` field. The added condition ensures we never process more than `NFAPI_MAX_PHY_RF_INSTANCES` (typically 4-8 depending on build configuration), even if the request claims more. This follows defensive programming practices and aligns with the array sizing used throughout the nFAPI codebase.

### Testing
- Verified PNF initialization with valid config requests containing 1-4 PHY-RF instances
- Tested rejection of malformed requests with excessive instance counts
- Confirmed no regression in existing NR and LTE PNF bringup procedures