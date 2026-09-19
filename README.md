# ECE 298A Tiny Tapeout Demo

An SPI-configurable 8-bit counter designed for the [Tiny Tapeout](https://tinytapeout.com/) digital interface. The design accepts write-only configuration frames, supports four counter modes, and exposes the result on the eight dedicated output pins.

## Features

- 8-bit up, down, Gray-code, and programmable-step counting
- Configurable start, set, and end values
- Per-bit output enable mask
- Runtime pause, restart, and direct-load controls
- 11-bit, MSB-first SPI-style configuration interface
- Asynchronous reset assertion with synchronous deassertion inside each module

## Architecture

```text
                     11-bit configuration frame
COPI, SCLK, CS_n  ─────────► spi_in ─────────► confinfo
                                                 │
                                                 │ 41-bit configuration bus
                                                 ▼
Tiny Tapeout clk, rst_n ─────────────────────► counter ─────► uo_out[7:0]
```

The RTL is split into the following files:

| File | Purpose |
| --- | --- |
| `src/project.v` | Tiny Tapeout wrapper and external pin mapping |
| `src/top.v` | Connects the SPI receiver, configuration registers, and counter |
| `src/spi_in.v` | Synchronizes the serial inputs and receives 11-bit frames |
| `src/confinfo.v` | Stores configuration registers and generates load pulses |
| `src/counter.v` | Implements the four counter modes and output mask |
| `src/config.json` | LibreLane hardening configuration |

## Pinout

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

The bidirectional pins are unused: `uio_out` and `uio_oe` are driven low. The Tiny Tapeout `ena` input is not used by the counter logic.

## Configuration interface

The interface is SPI-like and write-only; there is no return-data signal. Hold `CS_n` low while sending one complete 11-bit frame:

```text
bit 10                                      bit 0
┌───────────────┬───────────────────────────────┐
│ address [2:0] │          data [7:0]           │
└───────────────┴───────────────────────────────┘
       MSB first, sampled on rising SCLK edges
```

`clk` must run substantially faster than `SCLK` because `SCLK`, `COPI`, and `CS_n` cross into the `clk` domain through synchronizer stages. Deassert `CS_n` between frames so the receiver returns to the beginning of a word.

For software, a frame can be assembled as:

```text
frame = (address << 8) | data
```

Transmit exactly 11 bits, from bit 10 through bit 0.

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

The `MODE` field is encoded in `data[7:6]`:

| Value | Mode | Behaviour |
| --- | --- | --- |
| `00` | Up | Increments the binary counter by 1; when the current value is at or above `END_VALUE`, the next value is `START_VALUE` |
| `01` | Down | Decrements the binary counter by 1; when the current value is at or below `END_VALUE`, the next value is `START_VALUE` |
| `10` | Gray | Counts upward internally and presents `binary ^ (binary >> 1)` on the outputs |
| `11` | Count-by | Adds or subtracts the programmed magnitude and uses the corresponding up/down terminal comparison |

For `COUNT_BY`, `data[7] = 1` selects addition and `data[7] = 0` selects subtraction. The magnitude is the unsigned four-bit value in `data[6:3]` (0–15). This describes the current RTL behaviour.

### Control writes

| Data | Meaning |
| --- | --- |
| `0x00` | Pause counting |
| `0x40` | Run/resume counting |
| `0x80` | Load `START_VALUE` and remain paused |
| `0xC0` | Load `START_VALUE` and run |

A write to `SET_VALUE` immediately requests a load of that value. If restart and set-value loads coincide, restart has priority; both have priority over normal counting.

## Example configuration

The following sequence configures an up-counter from `0x10` through `0x1F`, enables all output bits, loads the start value, and begins counting:

| Frame | Address | Data | Action |
| --- | --- | --- | --- |
| `0x010` | `000` | `0x10` | Set start value to `0x10` |
| `0x21F` | `010` | `0x1F` | Set end value to `0x1F` |
| `0x300` | `011` | `0x00` | Select up-counting mode |
| `0x5FF` | `101` | `0xFF` | Enable all eight outputs |
| `0x6C0` | `110` | `0xC0` | Restart from `0x10` and run |

Each hexadecimal frame above represents an 11-bit value; transmit only bits 10 down to 0.

## Reset and startup

Drive `rst_n` low to reset the design. Reset assertion is asynchronous, while release is synchronized to `clk` through two flip-flops. Allow at least two rising `clk` edges after releasing `rst_n` before sending configuration data.

The counter itself resets to `0x00`. Configure the registers, output-enable mask, and control register before relying on the outputs.

## Simulation

The repository uses [cocotb](https://www.cocotb.org/) with Icarus Verilog by default:

```sh
cd test
python3 -m pip install -r requirements.txt
make -B
```

To view the generated waveform:

```sh
gtkwave tb.fst tb.gtkw
```

## Current development status

The counter architecture and serial register map are present, but the repository still contains pieces of the original Tiny Tapeout adder template. Before the standard simulation and hardening workflows can pass, the following integration work remains:

- Add `top.v`, `spi_in.v`, `confinfo.v`, and `counter.v` to `project.source_files` in `info.yaml` and to `PROJECT_SOURCES` in `test/Makefile`.
- Remove the template `assign uo_out = ui_in + uio_in` assignment in `src/project.v`; it currently drives `uo_out` at the same time as the counter.
- Replace the template adder check in `test/test.py` with SPI configuration and counter-mode tests.
- Replace the procedural per-bit `assign` statements in `src/counter.v` with synthesizable combinational output logic. The current form fails Icarus Verilog elaboration because the bit select is not constant in that context.
- Reset `operating_vals` in `src/confinfo.v` so the run state is defined after reset.
- Update the `info.yaml` pin names to match `COPI`, `SCLK`, and `CS_n` rather than the placeholder UART label.

## External hardware

No design-specific peripheral is required. On a Tiny Tapeout board, configuration can be driven by a microcontroller, FPGA, or logic-pattern generator that provides `COPI`, `SCLK`, and active-low `CS_n`. Ensure the controller shares ground with the board and keeps the serial clock slower than the Tiny Tapeout system clock.

## License

This project is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).
