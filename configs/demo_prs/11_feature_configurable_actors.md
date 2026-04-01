## Title: Make number of UL/DL actors in NR UE fully configurable

### Summary
The nr-uesoftmodem previously used hardcoded values for the number of uplink and downlink processing actors (threads) in the NR UE data path. The UL actor count was fixed at 2 and the DL actor count at 4, baked into compile-time constants in the UE main initialization. This prevented deployment flexibility: low-power platforms needed fewer actors to avoid context switching overhead, while high-core-count servers could benefit from higher parallelism for multi-UE simulations.

This patch makes both values runtime-configurable via the OAI configuration framework. Two new parameters, `num_ul_actors` and `num_dl_actors`, are added to the `[NR_UE]` configuration section, defaulting to 2 and 4 respectively for backward compatibility. Values are validated at startup to be within [1, 16].

### Changes
- `executables/nr-uesoftmodem.c`: Added `num_ul_actors` and `num_dl_actors` to the NR UE parameter table with defaults of 2 and 4. Added range validation (1-16) during parameter parsing. Passed values to the UE initialization functions.
- `openair2/LAYER2/NR_MAC_UE/main_ue_nr.c`: Replaced `NR_UL_ACTORS` and `NR_DL_ACTORS` compile-time constants with runtime parameters received from the configuration. Updated actor pool initialization loop to use the configured counts.
- `openair2/LAYER2/NR_MAC_UE/mac_defs.h`: Removed `#define NR_UL_ACTORS 2` and `#define NR_DL_ACTORS 4`. Added `num_ul_actors` and `num_dl_actors` fields to `NR_UE_MAC_INST_t`.
- `openair1/PHY/defs_nr_UE.h`: Added `nr_ul_actors` and `nr_dl_actors` fields to `PHY_VARS_NR_UE` struct so the PHY layer can query the configured actor count for its own thread pool sizing.

### Testing
- Tested with `num_ul_actors=1, num_dl_actors=1` on a Raspberry Pi 4: UE successfully registers and sustains 5 Mbps DL throughput without actor thread starvation.
- Tested with `num_ul_actors=8, num_dl_actors=8` on a 32-core server running 4 UE instances in parallel via rfsimulator: all 4 UEs register and sustain full throughput.
- Confirmed default behavior (no config change) matches pre-patch behavior via the standard `nr-sa-rfsim` CI test.
