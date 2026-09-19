import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, ReadOnly

# Configuration register addresses
START_VALUE   = 0b000
END_VALUE     = 0b010
MODE          = 0b011
OUTPUT_ENABLE = 0b101
CONTROL       = 0b110


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


@cocotb.test()
async def test_basic_counter(dut):
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    # init inputs
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = pack_ui(cs_n=1)
    dut.rst_n.value = 0

    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 4)

    await spi_write(dut, START_VALUE, 0)
    await spi_write(dut, END_VALUE, 3)
    await spi_write(dut, MODE, 0b00 << 6)
    await spi_write(dut, OUTPUT_ENABLE, 0xFF)

    # load START_VALUE but remain paused.
    await spi_write(dut, CONTROL, 0x80)
    await ReadOnly()

    assert int(dut.uo_out.value) == 0, f"Expected restart value 0, got {dut.uo_out.value}"

    # enable count
    await spi_write(dut, CONTROL, 0x40)
    await ReadOnly()

    previous = int(dut.uo_out.value)

    # check increment
    for _ in range(8):
        observed = await sample_output(dut)
        expected = 0 if previous >= 3 else previous + 1

        assert observed == expected, (f"Expected {expected}, got {observed}; " 
                                      f"previous value was {previous}")

        previous = observed

    # pause
    await spi_write(dut, CONTROL, 0x00)
    await ReadOnly()

    held_value = int(dut.uo_out.value)

    # confirm no change in value
    for _ in range(4):
        observed = await sample_output(dut)
        assert observed == held_value, ( f"Counter should be paused at {held_value}, " 
                                        f"but changed to {observed}")