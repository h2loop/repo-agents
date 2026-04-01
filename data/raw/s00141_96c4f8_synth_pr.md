## Title: Fix T3418 timer duration to comply with 3GPP specifications

### Summary
Correct the default value of the NAS timer T3418 from 20 seconds to 30 seconds to align with 3GPP TS 24.301 requirements. The previous configuration caused the UE to prematurely timeout authentication and security mode procedures, potentially leading to registration failures or unnecessary re-authentication attempts when the network was operating within specification-compliant timing.

### Changes
- `openair3/NAS/UE/EMM/emmData.h`: Updated `T3418_DEFAULT_VALUE` from `20` to `30` seconds

### Implementation Details
This change modifies a single macro definition that defines the default timeout period for the T3418 authentication timer in the UE NAS layer. The timer is activated when the UE initiates authentication procedures and should allow sufficient time for network processing and radio propagation delays. The 30-second value matches the mandatory minimum specified in 3GPP TS 24.301 section 10.2, ensuring interoperability with compliant network implementations.

### Testing
- Verified timer initialization uses the updated default value during UE attach procedure
- Confirmed no regression in basic registration flow with Open5GS core network
- Validated that authentication procedures now complete successfully under normal network response conditions without premature timeout

---