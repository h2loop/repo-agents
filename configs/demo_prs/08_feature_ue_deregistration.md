## Title: Add telnet command to trigger UE-initiated deregistration

### Summary
There was previously no runtime mechanism to trigger a UE-initiated deregistration from the nr-uesoftmodem process without terminating it. This made it difficult to test RRC Inactive and RRC Idle state transitions in CI, and debugging the deregistration message flow required restarting the entire UE process.

This patch adds a `dereg` command to the telnet server's NR UE command set. When invoked, the command triggers a UE-initiated deregistration procedure by signaling the NAS layer to send a Deregistration Request (type: switch off) to the AMF. The command accepts an optional `--type` argument to select between "switch-off" (default) and "normal" deregistration types, corresponding to the 3GPP TS 24.501 Section 8.2.12 deregistration variants. After the deregistration completes, the UE transitions to RRC Idle and the nr-uesoftmodem process remains running, ready for a subsequent registration trigger.

### Changes
- `common/utils/telnetsrv/telnetsrv_ciUE.c`: Added `ue_dereg_cmd()` handler function and registered the `dereg` command in the UE telnet command table with help text and argument parsing for `--type`.
- `openair3/NAS/NR_UE/nr_nas_msg.c`: Added `nr_nas_trigger_deregistration()` public function that constructs and sends a Deregistration Request UE Originating message via the NAS uplink path.
- `openair3/NAS/NR_UE/nr_nas_msg.h`: Added prototype for `nr_nas_trigger_deregistration()` with the `deregistration_type_t` enum parameter.
- `openair3/NAS/NR_UE/5GS/5GMM/MSG/FGSDeregistrationRequestUEOriginating.c`: Minor fix to correctly encode the de-registration type IE "switch off" bit when triggered programmatically rather than from process shutdown.

### Testing
- Manual test: started nr-uesoftmodem with rfsimulator, performed registration, issued `dereg` via telnet, confirmed Deregistration Request sent and Deregistration Accept received in NAS traces.
- CI test: added a new step to the `nr-sa-attach-detach` pipeline that performs registration, iperf, telnet deregistration, re-registration, and verifies all transitions succeed.
- Confirmed RRC state transitions (Connected -> Idle) occur correctly by checking RRC logs after deregistration.
