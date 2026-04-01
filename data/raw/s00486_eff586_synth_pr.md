## Title: Fix UL MIMO configuration mismatch in NR MAC gNB

### Summary
The PUSCH configuration logic in the NR MAC gNB was hardcoding uplink MIMO parameters (`maxRank = 1` and `codebookSubset = nonCoherent`) regardless of UE capabilities. This created a configuration mismatch between protocol layers where the gNB would configure single-layer operation even for UEs that support multi-layer UL MIMO, causing inconsistent behavior in downstream scheduling and link adaptation logic.

This fix parses UE capability information to determine the actual number of supported UL layers and configures both `maxRank` and `codebookSubset` appropriately. For UEs supporting multiple UL layers, the codebook subset is set to `partialAndNonCoherent` to enable better spatial multiplexing performance, while single-layer UEs retain the `nonCoherent` setting.

### Changes
- `openair2/LAYER2/NR_MAC_gNB/nr_radio_config.c`: Enhanced PUSCH configuration in `config_pusch()` to derive `ul_max_layers` from `featureSetsUplinkPerCC` UE capabilities. Set `maxRank` to the derived layer count and select `codebookSubset` based on layer support (multi-layer → `partialAndNonCoherent`, single-layer → `nonCoherent`).

### Implementation Details
The implementation checks for valid UE capability structures (`uecap->featureSets->featureSetsUplinkPerCC`) and extracts `maxNumberMIMO_LayersCB_PUSCH` to determine supported layers (1, 2, or 4). Default fallback to single-layer ensures backward compatibility when UE capabilities are unavailable. This ensures MAC layer configuration aligns with PHY capabilities and UE-reported features, eliminating the layer mismatch.