<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

Note: AI was used to generate much of the formatting and information in this section.

### Features

- 8-bit up, down, Gray-code, and programmable-step counting
- Configurable start, set, and end values
- Per-bit output enable mask
- Runtime pause, restart, and direct-load controls
- 11-bit, MSB-first SPI-style configuration interface
- Asynchronous reset assertion with synchronous deassertion inside each module

### Dedicated inputs

| Tiny Tapeout pin | Signal | Description |
| --- | --- | --- |
| `ui_in[0]` | `COPI` | Controller-out/peripheral-in serial data |
| `ui_in[1]` | `SCLK` | Serial clock; data is captured on its rising edge |
| `ui_in[2]` | `CS_n` | Active-low chip select |
| `ui_in[7:3]` | — | Unused |

### Dedicated outputs

| Tiny Tapeout pin | Signal | Description |
| --- | --- | --- |
| `uo_out[7:0]` | `counter[7:0]` | Binary or Gray-code counter value, subject to the output-enable mask |

### Configuration interface

The interface is an SPI-like write-only signal. Data is input in 11 bit frames, MSB first, with data sampled on the SPI rising edge.

```
bit 10                                      bit 0
┌───────────────┬───────────────────────────────┐
│ address [2:0] │          data [7:0]           │
└───────────────┴───────────────────────────────┘
```

`clk` must run substantially faster than `SCLK` because `SCLK`, `COPI`, and `CS_n` are handled in the `clk` domain, and do not operate tied to SCLK. 

## Register map

| Address | Name | Data format | Effect |
| --- | --- | --- | --- |
| `000` | `START_VALUE` | `data[7:0]` | Value loaded by a restart command and after a terminal-count wrap |
| `001` | `SET_VALUE` | `data[7:0]` | Stores the value and generates a one-cycle pulse that loads it into the counter |
| `010` | `END_VALUE` | `data[7:0]` | Terminal value used by the selected counter mode |
| `011` | `MODE` | `data[7:6]` | Selects up, down, Gray, or programmable-step mode; `data[5:0]` is ignored |
| `100` | `COUNT_BY` | `data[7]` direction, `data[6:3]` magnitude | Step used in programmable-step mode; `data[2:0]` is ignored |
| `101` | `OUTPUT_ENABLE` | `data[7:0]` | Per-bit output mask; `1` drives the corresponding output and `0` drives high impedance |
| `110` | `CONTROL` | `data[7]` restart, `data[6]` run | Updates control state; `data[5:0]` is ignored |
| `111` | Reserved | — | No effect |

### Counter modes

| Value | Mode | Behaviour |
| --- | --- | --- |
| `00` | Up | Increments the binary counter by 1; when the current value is at or above `END_VALUE`, the next value is `START_VALUE` |
| `01` | Down | Decrements the binary counter by 1; when the current value is at or below `END_VALUE`, the next value is `START_VALUE` |
| `10` | Gray | Increments the binary counter by 1; when the current value is at or above `END_VALUE`, the next value is `START_VALUE`. Presents output in gray code. |
| `11` | Count-by | Acts as a up counter or down counter, depending on sign of `COUNT_BY`. Increment/decrement by magnitude of `COUNT_BY`.|

**For up counters, END_VALUE < START_VALUE is undefined. For down counters, START_VALUE < END_VALUE is undefined.**

### Control writes

| Data | Meaning |
| --- | --- |
| `0x00` | Pause counting |
| `0x40` | Run/resume counting |
| `0x80` | Set counter to `START_VALUE` and remain paused |
| `0xC0` | Set counter to `START_VALUE` and run |

Note, restart and setting values are "toggled" values, and will only be acted on once when initially set. You do not need to clear restart or `SET_VALUE` signals.

## How to test

ask claude

## External hardware

no external hardware
