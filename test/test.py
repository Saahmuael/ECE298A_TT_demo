import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, ReadOnly

GATE_LEVEL = os.getenv("GATES", "no").lower() == "yes"

# Configuration register addresses
START_VALUE   = 0b000
SET_VALUE     = 0b001
END_VALUE     = 0b010
MODE          = 0b011
COUNT_BY      = 0b100
OUTPUT_ENABLE = 0b101
CONTROL       = 0b110

#MODE register values
MODE_UP       = 0b00 << 6
MODE_DOWN     = 0b01 << 6
MODE_GRAY     = 0b10 << 6
MODE_COUNT_BY = 0b11 << 6

# CONTROL register values 
STOP        = 0b00 << 6
START       = 0b01 << 6
STOP_RESET  = 0b10 << 6
START_RESET = 0b11 << 6

# config input bits for w-only SPI
def pack_ui(copi=0, sclk=0, cs_n=1):
    return (copi << 0) | (sclk << 1) | (cs_n << 2)

async def spi_write(dut, address, data):
    frame = ((address & 0b111) << 8) | (data & 0xFF)

    await RisingEdge(dut.clk)

    # select
    dut.ui_in.value = pack_ui(cs_n=0)
    await ClockCycles(dut.clk, 4)

    # Send frame.
    for bit_index in range(10, -1, -1):
        bit = (frame >> bit_index) & 1

        dut.ui_in.value = pack_ui(copi=bit, sclk=0, cs_n=0)
        await ClockCycles(dut.clk, 4)

        dut.ui_in.value = pack_ui(copi=bit, sclk=1, cs_n=0)
        await ClockCycles(dut.clk, 4)

        dut.ui_in.value = pack_ui(copi=bit, sclk=0, cs_n=0)

    # deselect
    dut.ui_in.value = pack_ui(cs_n=1)
    await ClockCycles(dut.clk, 6)


async def sample_output(dut):
    await RisingEdge(dut.clk)
    await ReadOnly()
    return int(dut.uo_out.value)

# compute gray code value
def gray(value):
    return value ^ (value >> 1)

# compute value to use in setting COUNT_BY
def count_by_value(up, magnitude):
    return ((1 if up else 0) << 7) | ((magnitude & 0xF) << 3)

# Return the counter value
def raw_count(dut):
    return int(dut.user_project.u_top.u_counter.count_bin.value)

# Return the value returned/broadcast by counter
def visible_value(mode, value):
    return gray(value) if mode == MODE_GRAY else value

# extract config
def extract_config(dut):
    top = dut.user_project.u_top
    cfg = int(top.cfg.value)

    return {
        "rst_n":   int(dut.rst_n.value),
        "start":   (cfg >> 33) & 0xFF,
        "setval":  (cfg >> 25) & 0xFF,
        "end":     (cfg >> 17) & 0xFF,
        "mode":    (cfg >> 15) & 0x03,
        "countby": (cfg >> 10) & 0x1F,
        "enable":  (cfg >> 2) & 0xFF,
        "run":     cfg & 1,
        "reset":   int(top.reset_indc.value),
        "set":     int(top.setval_indc.value),
    }

# Reference model
async def counter_model(dut, running):
    top = dut.user_project.u_top

    await ReadOnly()

    expected = int(top.u_counter.count_bin.value)
    previous_cfg = extract_config(dut)

    while running[0]: # use mutable value
        await RisingEdge(dut.clk)

        # use the configuration present before new edge.
        cfg = previous_cfg

        if not cfg["rst_n"]:
            expected = 0

        elif cfg["reset"]:
            expected = cfg["start"]

        elif cfg["set"]:
            expected = cfg["setval"]

        elif cfg["run"]:
            if cfg["mode"] in (MODE_UP >> 6, MODE_GRAY >> 6):  # Up or Gray
                if expected >= cfg["end"]:
                    expected = cfg["start"]
                else:
                    expected = (expected + 1) & 0xFF

            elif cfg["mode"] == MODE_DOWN >> 6:  # Down
                if expected <= cfg["end"]:
                    expected = cfg["start"]
                else:
                    expected = (expected - 1) & 0xFF

            else:  # Count-by
                step = cfg["countby"] & 0x0F
                count_up = bool(cfg["countby"] & 0x10)

                if count_up:
                    if expected >= cfg["end"]:
                        expected = cfg["start"]
                    else:
                        expected = (expected + step) & 0xFF
                else:
                    if expected <= cfg["end"]:
                        expected = cfg["start"]
                    else:
                        expected = (expected - step) & 0xFF

        await ReadOnly()

        actual = int(top.u_counter.count_bin.value)

        assert actual == expected, (
            f"Expected count 0x{expected:02x}, "
            f"got 0x{actual:02x}"
        )

        # uses the configuration visible after the edge.
        current_cfg = extract_config(dut)

        if current_cfg["enable"] == 0xFF:
            expected_output = expected

            if current_cfg["mode"] == MODE_GRAY >> 6:
                expected_output ^= expected_output >> 1

            assert int(dut.uo_out.value) == expected_output, (
                f"Expected output 0x{expected_output:02x}, "
                f"got {dut.uo_out.value}"
            )

        previous_cfg = current_cfg

async def reset_dut(dut):
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = pack_ui(cs_n=1)
    dut.rst_n.value = 0

    await ClockCycles(dut.clk, 5)

    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 4)


async def test_gate_level_counter(dut):
    """Exercise the counter using only signals preserved in the GL netlist."""
    await spi_write(dut, OUTPUT_ENABLE, 0xFF)
    await spi_write(dut, CONTROL, STOP)
    await spi_write(dut, START_VALUE, 0x2D)
    await spi_write(dut, END_VALUE, 0x31)
    await spi_write(dut, MODE, MODE_UP)
    await spi_write(dut, CONTROL, STOP_RESET)

    observed = await sample_output(dut)
    assert observed == 0x2D, (
        f"Reset should load 0x2d, got 0x{observed:02x}"
    )

    await spi_write(dut, SET_VALUE, 0x2F)
    observed = await sample_output(dut)
    assert observed == 0x2F, (
        f"SET_VALUE should load 0x2f, got 0x{observed:02x}"
    )

    await spi_write(dut, CONTROL, START)
    samples = [await sample_output(dut) for _ in range(10)]

    for previous, current in zip(samples, samples[1:]):
        expected = 0x2D if previous >= 0x31 else previous + 1
        assert current == expected, (
            f"Expected 0x{expected:02x} after 0x{previous:02x}, "
            f"got 0x{current:02x}"
        )

    await spi_write(dut, CONTROL, STOP)
    held = await sample_output(dut)

    for _ in range(3):
        observed = await sample_output(dut)
        assert observed == held, (
            f"Stopped counter changed from 0x{held:02x} "
            f"to 0x{observed:02x}"
        )


async def test_spi_regw(dut):
    conf = dut.user_project.u_top.u_confinfo

    writes = (
        (
            START_VALUE,
            0xA5,
            conf.startval,
            0xA5,
            "START_VALUE",
        ),
        (
            SET_VALUE,
            0x3C,
            conf.setval,
            0x3C,
            "SET_VALUE",
        ),
        (
            END_VALUE,
            0xD2,
            conf.endval,
            0xD2,
            "END_VALUE",
        ),
        (
            MODE,
            MODE_GRAY | 0x3F,
            conf.countertype,
            MODE_GRAY >> 6,
            "MODE",
        ),
        (
            COUNT_BY,
            0xD7,
            conf.countby,
            0x1A,
            "COUNT_BY",
        ),
        (
            OUTPUT_ENABLE,
            0xA5,
            conf.enable_out,
            0xA5,
            "OUTPUT_ENABLE",
        ),
        (
            CONTROL,
            STOP_RESET,
            conf.operating_vals,
            STOP_RESET >> 6,
            "CONTROL",
        ),
    )

    for address, written, signal, expected, name in writes:
        await spi_write(dut, address, written)

        observed = int(signal.value)

        assert observed == expected, (
            f"{name}: wrote 0x{written:02x}; expected stored value "
            f"0x{expected:02x}, got 0x{observed:02x}"
        )

async def test_rst_update(dut):
    # write values
    await spi_write(dut, OUTPUT_ENABLE, 0xFF)
    await spi_write(dut, START_VALUE, 0x2D)
    await spi_write(dut, END_VALUE, 0x7F)
    await spi_write(dut, MODE, MODE_UP)
    await spi_write(dut, CONTROL, STOP_RESET)

    # test if reset loads start
    assert raw_count(dut) == 0x2D, ("Reset did not load START_VALUE")
    assert int(dut.uo_out.value) == 0x2D

    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    # test reset is one shot
    assert raw_count(dut) == 0x2D, ("Reset must be a one-shot update")

    await spi_write(dut, SET_VALUE, 0x53)

    # test SET_VALUE updates the counter
    assert raw_count(dut) == 0x53, ("SET_VALUE write did not update the counter")
    assert int(dut.uo_out.value) == 0x53

    await ClockCycles(dut.clk, 3)
    await ReadOnly()

    # assert the counter holds values
    assert raw_count(dut) == 0x53, ("Paused counter did not hold SET_VALUE")

async def test_mode_rst(dut, case):
    # write init
    await spi_write(dut, CONTROL, STOP)
    await spi_write(dut, START_VALUE, case["start"])
    await spi_write(dut, END_VALUE, case["end"])

    if case["mode"] == MODE_COUNT_BY:
        await spi_write(
            dut,
            COUNT_BY,
            count_by_value(case["count_up"], case["step"]),
        )

    # stop and reset
    await spi_write(dut, MODE, case["mode"])
    await spi_write(dut, OUTPUT_ENABLE, 0xFF)
    await spi_write(dut, CONTROL, STOP_RESET)

    assert raw_count(dut) == case["start"]
    assert int(dut.uo_out.value) == visible_value(
        case["mode"],
        case["start"],
    )

    await spi_write(dut, CONTROL, START)
    await ClockCycles(dut.clk, case["wrap_cycles"])

async def test_modeswitch(dut, case):
    await spi_write(dut, CONTROL, STOP)
    await spi_write(dut, START_VALUE, case["switch_start"])
    await spi_write(dut, END_VALUE, case["switch_end"])
    await spi_write(dut, MODE, case["source_mode"])

    if (
        case["mode"] == MODE_COUNT_BY
        or case["source_mode"] == MODE_COUNT_BY
    ):
        await spi_write(
            dut,
            COUNT_BY,
            count_by_value(
                case["count_up"],
                case["step"],
            ),
        )

    await spi_write(dut, SET_VALUE, case["switch_value"])

    assert raw_count(dut) == case["switch_value"], (
        f'{case["name"]}: failed to load the mid-range value'
    )

    await spi_write(dut, CONTROL, START)
    await spi_write(dut, MODE, case["mode"])

    observed_mode = int(
        dut.user_project.u_top.u_confinfo.countertype.value
    )

    assert observed_mode == case["mode"] >> 6, (
        f'{case["name"]}: mid-count MODE write failed'
    )
    await ClockCycles(dut.clk, case["wrap_cycles"])



@cocotb.test()
async def test_counter(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    if GATE_LEVEL:
        await test_gate_level_counter(dut)
        return

    model_running = [True]
    model_task = cocotb.start_soon(
        counter_model(dut, model_running)
    )

    await test_spi_regw(dut)
    await test_rst_update(dut)

    cases = (
        dict(
            name="up",
            start=0xFC,
            end=0xFF,
            mode=MODE_UP,
            step=1,
            count_up=True,
            wrap_cycles=8,
            source_mode=MODE_GRAY,
            switch_start=0x10,
            switch_end=0xF0,
            switch_value=0x40,
        ),
        dict(
            name="down",
            start=0x03,
            end=0x00,
            mode=MODE_DOWN,
            step=1,
            count_up=False,
            wrap_cycles=8,
            source_mode=MODE_COUNT_BY,
            switch_start=0xF0,
            switch_end=0x10,
            switch_value=0xC0,
        ),
        dict(
            name="gray",
            start=0xFC,
            end=0xFF,
            mode=MODE_GRAY,
            step=1,
            count_up=True,
            wrap_cycles=8,
            source_mode=MODE_UP,
            switch_start=0x10,
            switch_end=0xF0,
            switch_value=0x40,
        ),
        dict(
            name="count-by up",
            start=0xF9,
            end=0xFF,
            mode=MODE_COUNT_BY,
            step=3,
            count_up=True,
            wrap_cycles=7,
            source_mode=MODE_UP,
            switch_start=0x10,
            switch_end=0xF0,
            switch_value=0x40,
        ),
        dict(
            name="count-by down",
            start=0x06,
            end=0x00,
            mode=MODE_COUNT_BY,
            step=3,
            count_up=False,
            wrap_cycles=7,
            source_mode=MODE_DOWN,
            switch_start=0xF0,
            switch_end=0x10,
            switch_value=0xC0,
        ),
    )

    for case in cases:
        dut._log.info(
            "Testing %s mode from restart through wrap",
            case["name"],
        )
        await test_mode_rst(dut, case)

        dut._log.info(
            "Testing mid-count switch to %s mode",
            case["name"],
        )
        await test_modeswitch(dut, case)

    await spi_write(dut, CONTROL, STOP)

    model_running[0] = False
    await model_task

# @cocotb.test()
# async def test_basic_counter(dut):
#     clock = Clock(dut.clk, 10, unit="ns")
#     cocotb.start_soon(clock.start())

#     # init inputs
#     dut._log.info(f"uo_out = {dut.uo_out.value}")
#     dut.ena.value = 1
#     dut.uio_in.value = 0
#     dut.ui_in.value = pack_ui(cs_n=1) 
#     dut.rst_n.value = 0

#     await ClockCycles(dut.clk, 5)
#     dut.rst_n.value = 1
#     await ClockCycles(dut.clk, 4)

#     # print(f"Made it to spi write START")
#     await spi_write(dut, START_VALUE, 0)
#     # assert (dut.user_project.u_top.u_confinfo.startval.value) == 0, f"expected 0, got {dut.user_project.u_top.u_confinfo.startval.value}"

#     # print(f"Made it to spi write END")
#     await spi_write(dut, END_VALUE, 3)
#     # assert (dut.user_project.u_top.u_confinfo.endval.value) == 3, f"expected {3}, got {dut.user_project.u_top.u_confinfo.endval.value}"

#     # print(f"Made it to spi write MODE")
#     await spi_write(dut, MODE, 0)
#     # assert (dut.user_project.u_top.u_confinfo.countertype.value) == 0, f"expected 0, got {dut.user_project.u_top.u_confinfo.countertype.value}"
    
#     # print(f"Made it to spi write ENABLE")
#     await spi_write(dut, OUTPUT_ENABLE, 0xFF)
#     # assert (dut.user_project.u_top.u_confinfo.enable_out.value) == 0xFF, f"expected 0xFF, got {dut.user_project.u_top.u_confinfo.operating_vals.value}"
    
#     # dut._log.info(f"cfg            = {dut.user_project.u_top.u_counter.cfg.value}")
#     # dut._log.info(f"startval       = {dut.user_project.u_top.u_counter.startval.value}")
#     # dut._log.info(f"endval         = {dut.user_project.u_top.u_counter.endval.value}")
#     # dut._log.info(f"countertype    = {dut.user_project.u_top.u_counter.countertype.value}")
#     # dut._log.info(f"countby        = {dut.user_project.u_top.u_counter.countby.value}")
#     # dut._log.info(f"enable_out     = {dut.user_project.u_top.u_counter.enable_out.value}")
#     # dut._log.info(f"operating_vals = {dut.user_project.u_top.u_counter.operating_vals.value}")
#     # dut._log.info(f"count_bin      = {dut.user_project.u_top.u_counter.count_bin.value}")

#     # load START_VALUE but remain paused.
#     await spi_write(dut, CONTROL, 0x80)
#     await ReadOnly()

#     assert int(dut.uo_out.value) == 0, f"Expected restart value 0, got {dut.uo_out.value}"

#     # enable count
#     await spi_write(dut, CONTROL, 0x40)
#     await ReadOnly()

#     previous = int(dut.uo_out.value)

#     # check increment
#     for _ in range(8):
#         dut._log.info(f"uo_out = {dut.uo_out.value}")
#         observed = await sample_output(dut)
#         expected = 0 if previous >= 3 else previous + 1

#         assert observed == expected, (f"Expected {expected}, got {observed}; previous value was {previous}")

#         previous = observed
    
#     # pause
#     await spi_write(dut, CONTROL, 0x00)
#     await ReadOnly()

#     held_value = int(dut.uo_out.value)

#     # confirm no change in value
#     for _ in range(4):
#         observed = await sample_output(dut)
#         assert observed == held_value, ( f"Counter should be paused at {held_value}; but changed to {observed}")
