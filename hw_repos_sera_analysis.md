# SERA-Suitable Repos for Embedded Low-Level Hardware Development

## Overview

Analysis of 818 repos from `Generic_scraped.csv`, cross-referenced with live GitHub stats (stars, forks, open issues, open/closed/merged PRs), filtered for **embedded, hardware-dependent, low-level programming** suitability for SERA-style data generation.

**Date:** 2026-02-16

---

## Selection Criteria

A repo is considered ideal for SERA + low-level embedded work when it satisfies:

1. **C/C++ codebase** — SERA's tree-sitter pipeline extracts C/C++ functions
2. **Direct hardware interaction** — register-level access, peripheral drivers, HAL, bare-metal code
3. **High merged PR count** — needed to curate 10–20 demonstration PRs for synthetic PR generation
4. **High merge ratio** — indicates meaningful, non-noisy PRs
5. **Well-structured subsystems** — arch/, drivers/, boards/, subsys/ enable diverse function sampling
6. **Active maintenance** — stars and forks as community health proxies
7. **Domain-specific bug complexity** — memory management, concurrency, DMA, interrupt handling, protocol state machines

---

## Top 10 Repos

### 1. zephyrproject-rtos/zephyr

| Metric | Value |
|--------|-------|
| Stars | 14,475 |
| Forks | 8,654 |
| Merged PRs | 61,106 |
| Total Closed PRs | 72,891 |
| Merge Rate | 84% |
| Open Issues | 2,189 |
| HW Pairing | LIS2DE12 accelerometer (STMicroelectronics) — Sensor/Accelerometer |

**Why:** RTOS with device drivers, HAL, device tree bindings, subsystems (BLE, USB, networking, shell, logging). Pure C. Closest analogue to the OAI5G case study in the SERA paper. Best overall candidate.

---

### 2. apache/nuttx

| Metric | Value |
|--------|-------|
| Stars | 3,699 |
| Forks | 1,485 |
| Merged PRs | 15,515 |
| Total Closed PRs | 16,729 |
| Merge Rate | 93% |
| Open Issues | 639 |
| HW Pairing | S32K1xx FlexCAN (NXP Semiconductors) — Network/CAN Controller |

**Why:** POSIX-compliant RTOS. Arch-specific startup code, board BSPs, char/block drivers, filesystems, scheduling. Pure C. Highest merge rate in the list — PRs are clean and meaningful.

---

### 3. RT-Thread/rt-thread

| Metric | Value |
|--------|-------|
| Stars | 11,779 |
| Forks | 5,351 |
| Merged PRs | 7,135 |
| Total Closed PRs | 9,257 |
| Merge Rate | 77% |
| Open Issues | 326 |
| HW Pairing | GD5F4GQ4 flash (GigaDevice Semiconductor) — Memory/Flash |

**Why:** RTOS with 400+ BSPs, device framework (GPIO, SPI, I2C, UART, DMA, ADC), networking stack. Pure C. Massive subsystem diversity for function sampling.

---

### 4. ARMmbed/mbed-os

| Metric | Value |
|--------|-------|
| Stars | 4,829 |
| Forks | 3,046 |
| Merged PRs | 9,251 |
| Total Closed PRs | 10,980 |
| Merge Rate | 84% |
| Open Issues | 194 |
| HW Pairing | W74M12JV flash (Winbond Electronics) — Memory/Flash |

**Why:** Embedded OS with HAL for ARM Cortex-M, RTOS layer, peripheral drivers (SPI, I2C, UART, CAN), connectivity, storage, security. C/C++. Clear subsystem boundaries.

---

### 5. openthread/openthread

| Metric | Value |
|--------|-------|
| Stars | 3,884 |
| Forks | 1,141 |
| Merged PRs | 8,631 |
| Total Closed PRs | 9,514 |
| Merge Rate | 91% |
| Open Issues | 75 |
| HW Pairing | CC2651R (Texas Instruments) — Network/Bluetooth (BT Classic/BLE) |

**Why:** Thread mesh networking protocol stack. Radio abstraction layer, MAC, MLE, CoAP, platform ports. Pure C. Highly structured codebase with excellent merge rate.

---

### 6. FreeRTOS/FreeRTOS-Kernel

| Metric | Value |
|--------|-------|
| Stars | 3,869 |
| Forks | 1,450 |
| Merged PRs | 872 |
| Total Closed PRs | 1,067 |
| Merge Rate | 82% |
| Open Issues | 29 |
| HW Pairing | TMS570LS0432-Q1 (Texas Instruments) — MCU/Automotive MCU |

**Why:** Industry-standard RTOS kernel. Task scheduler, queues, semaphores, timers, memory allocators, port-specific assembly/C. Paired with TI automotive MCU — safety-critical embedded code. Smaller codebase but very high-quality pure C.

---

### 7. micropython/micropython

| Metric | Value |
|--------|-------|
| Stars | 21,469 |
| Forks | 8,712 |
| Merged PRs | 2,758 |
| Total Closed PRs | 7,091 |
| Merge Rate | 39% |
| Open Issues | 1,383 |
| HW Pairing | RP2350B (Raspberry Pi Foundation) — Compute/MCU (Real-time MCU) |

**Why:** MCU firmware-level code — machine module exposes GPIO, SPI, I2C, UART, ADC, PWM directly. Ports for STM32, ESP32, RP2, NRF, SAMD. Paired with RP2350B. Very high stars (21K). Lower merge rate due to volume of external contributions.

---

### 8. tock/tock

| Metric | Value |
|--------|-------|
| Stars | 6,225 |
| Forks | 804 |
| Merged PRs | 3,474 |
| Total Closed PRs | 3,921 |
| Merge Rate | 89% |
| Open Issues | 126 |
| HW Pairing | RM48L952-Q1 (Texas Instruments) — MCU/Automotive MCU |

**Why:** Embedded OS with capsule-based architecture. Kernel, chip HAL layers, board configurations, interrupt handling. Paired with TI automotive MCU. Note: primarily Rust, but has C HAL interface layers. May need scoping for SERA's C/C++ extraction.

---

### 9. espressif/esp-idf

| Metric | Value |
|--------|-------|
| Stars | 17,338 |
| Forks | 8,105 |
| Merged PRs | 329 |
| Total Closed PRs | 2,063 |
| Merge Rate | 16% |
| Open Issues | 1,382 |
| HW Pairing | IS67WVE4M16BLL (ISSI) — Memory/External RAM |

**Why:** Espressif's official ESP32 SDK. Peripheral drivers, Wi-Fi/BLE stack, bootloader, partition tables, flash encryption. Massive C codebase (17K stars). **Caveat:** Very low merged PRs (329) — most development happens internally. Weak for SERA's demo PR curation phase.

---

### 10. libopencm3/libopencm3

| Metric | Value |
|--------|-------|
| Stars | 3,499 |
| Forks | 1,105 |
| Merged PRs | 198 |
| Total Closed PRs | 935 |
| Merge Rate | 21% |
| Open Issues | 146 |
| HW Pairing | RM57L843-Q1 (Texas Instruments) — MCU/Automotive MCU |

**Why:** Bare-metal firmware library for ARM Cortex-M — direct MMIO register definitions, peripheral drivers for STM32/LPC/SAM/EFM32. About as low-level as it gets. **Caveat:** Low merged PRs (198) and low merge rate (21%) — limited demo PR material for SERA.

---

## Trade-offs Summary

| Repo | Strength | Weakness |
|------|----------|----------|
| zephyrproject-rtos/zephyr | Best all-around: 61K merged PRs, massive driver/subsystem diversity | Very large — may need subsystem scoping |
| apache/nuttx | Highest merge rate (93%), clean POSIX-compliant RTOS | Smaller community (3.7K stars) |
| RT-Thread/rt-thread | 400+ BSPs, great subsystem diversity | Lower merge rate (77%) |
| ARMmbed/mbed-os | Strong HAL + RTOS + drivers, 84% merge rate | Project is in maintenance mode |
| openthread/openthread | Clean protocol stack, 91% merge rate | Narrower domain (Thread networking only) |
| FreeRTOS/FreeRTOS-Kernel | Industry standard, safety-critical | Smaller codebase (872 merged PRs) |
| micropython/micropython | 21K stars, multi-platform MCU ports | 39% merge rate, mixed Python/C |
| tock/tock | Good merge rate (89%), automotive MCU pairing | Primarily Rust — limited C/C++ for SERA |
| espressif/esp-idf | 17K stars, huge C codebase, real HW drivers | Only 329 merged PRs — internal dev workflow |
| libopencm3/libopencm3 | Purest bare-metal register-level code | Only 198 merged PRs, 21% merge rate |

---

## Recommendation

**For SERA data generation, prioritize these 5:**

1. **zephyrproject-rtos/zephyr** — best overall
2. **apache/nuttx** — cleanest PR workflow
3. **RT-Thread/rt-thread** — broadest BSP/driver diversity
4. **ARMmbed/mbed-os** — strong HAL + RTOS combination
5. **openthread/openthread** — clean C protocol stack

These combine the deepest hardware interaction with the strongest PR workflows, making them ideal for SERA's function extraction, bug prompt taxonomy, synthetic PR generation, and soft verification pipeline.

---

## Data Sources

- **Repo metadata:** `Generic_scraped.csv` (818 entries with component/manufacturer/category pairings)
- **GitHub stats:** `repo_stats.csv` (fetched via GitHub GraphQL API on 2026-02-16)
- **SERA methodology:** SERA Paper.pdf (Soft-Verified Efficient Repository Agents)
