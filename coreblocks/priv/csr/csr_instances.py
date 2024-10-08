from amaranth import *

from typing import Optional
from coreblocks.arch import CSRAddress
from coreblocks.arch.isa import Extension
from coreblocks.params.genparams import GenParams
from coreblocks.priv.csr.csr_register import CSRRegister
from coreblocks.priv.csr.aliased import AliasedCSR
from transactron.core import Method, Transaction, def_method, TModule


class DoubleCounterCSR(Elaboratable):
    """DoubleCounterCSR
    Groups two `CSRRegisters` to form counter with double `isa.xlen` width.

    Attributes
    ----------
    increment: Method
        Increments the counter by 1. At overflow, counter value is set to 0.
    """

    def __init__(self, gen_params: GenParams, low_addr: CSRAddress, high_addr: Optional[CSRAddress] = None):
        """
        Parameters
        ----------
        gen_params: GenParams
            Core generation parameters.
        low_addr: CSRAddress
            Address of the CSR register representing lower part of the counter (bits `[isa.xlen-1 : 0]`).
        high_addr: CSRAddress or None, optional
            Address of the CSR register representing higher part of the counter (bits `[2*isa.xlen-1 : isa.xlen]`).
            If high_addr is None or not provided, then higher CSR is not synthetised and only the width of
            low_addr CSR is available to the counter.
        """
        self.gen_params = gen_params

        self.increment = Method()

        self.register_low = CSRRegister(low_addr, gen_params)
        self.register_high = CSRRegister(high_addr, gen_params) if high_addr is not None else None

    def elaborate(self, platform):
        m = TModule()

        m.submodules.register_low = self.register_low
        if self.register_high is not None:
            m.submodules.register_high = self.register_high

        @def_method(m, self.increment)
        def _():
            register_read = self.register_low.read(m).data
            self.register_low.write(m, data=register_read + 1)

            if self.register_high is not None:
                with m.If(register_read == (1 << self.gen_params.isa.xlen) - 1):
                    self.register_high.write(m, data=self.register_high.read(m).data + 1)

        return m


class MachineModeCSRRegisters(Elaboratable):
    def __init__(self, gen_params: GenParams):
        self.mvendorid = CSRRegister(CSRAddress.MVENDORID, gen_params, reset=0)
        self.marchid = CSRRegister(CSRAddress.MARCHID, gen_params, reset=gen_params.marchid)
        self.mimpid = CSRRegister(CSRAddress.MIMPID, gen_params, reset=gen_params.mimpid)
        self.mhartid = CSRRegister(CSRAddress.MHARTID, gen_params, reset=0)
        self.mscratch = CSRRegister(CSRAddress.MSCRATCH, gen_params)
        self.mconfigptr = CSRRegister(CSRAddress.MCONFIGPTR, gen_params, reset=0)

        self.mstatus = AliasedCSR(CSRAddress.MSTATUS, gen_params)

        self.mcause = CSRRegister(CSRAddress.MCAUSE, gen_params)

        # SPEC: The mtvec register must always be implemented, but can contain a read-only value.
        # set `MODE` as fixed to 0 - Direct mode "All exceptions set pc to BASE"
        self.mtvec = CSRRegister(CSRAddress.MTVEC, gen_params, ro_bits=0b11)

        mepc_ro_bits = 0b1 if Extension.C in gen_params.isa.extensions else 0b11  # pc alignment (SPEC)
        self.mepc = CSRRegister(CSRAddress.MEPC, gen_params, ro_bits=mepc_ro_bits)

    def elaborate(self, platform):
        m = Module()

        for name, value in vars(self).items():
            if isinstance(value, CSRRegister):
                m.submodules[name] = value

        return m


class GenericCSRRegisters(Elaboratable):
    def __init__(self, gen_params: GenParams):
        self.gen_params = gen_params

        self.m_mode = MachineModeCSRRegisters(gen_params)

        self.csr_cycle = DoubleCounterCSR(gen_params, CSRAddress.CYCLE, CSRAddress.CYCLEH)
        # TODO: CYCLE should be alias to TIME
        self.csr_time = DoubleCounterCSR(gen_params, CSRAddress.TIME, CSRAddress.TIMEH)

        if gen_params._generate_test_hardware:
            self.csr_coreblocks_test = CSRRegister(CSRAddress.COREBLOCKS_TEST_CSR, gen_params)

    def elaborate(self, platform):
        m = TModule()

        m.submodules.m_mode = self.m_mode

        m.submodules.csr_cycle = self.csr_cycle
        m.submodules.csr_time = self.csr_time
        if self.gen_params._generate_test_hardware:
            m.submodules.csr_coreblocks_test = self.csr_coreblocks_test

        with Transaction().body(m):
            self.csr_cycle.increment(m)
            self.csr_time.increment(m)

        return m
