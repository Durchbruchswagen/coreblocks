from coreblocks.func_blocks.fu.fpu.lza import *
from coreblocks.func_blocks.fu.fpu.fpu_common import FPUParams
from random import randint
from transactron import TModule
from transactron.lib import AdapterTrans
from transactron.testing import *
from amaranth import *


class TestLZA(TestCaseWithSimulator):
    class LZAModuleTest(Elaboratable):
        def __init__(self, params: FPUParams):
            self.params = params

        def elaborate(self, platform):
            m = TModule()
            m.submodules.lza = lza = self.lza_module = LZAModule(fpu_params=self.params)
            m.submodules.predict = self.predict_request_adapter = TestbenchIO(AdapterTrans(lza.predict_request))
            return m

    class HelpValues:
        def __init__(self, params: FPUParams):
            self.test_val_sig_a_1 = 16368512
            self.test_val_sig_b_1 = 409600
            self.test_val_sig_a_2 = 0
            self.test_val_sig_b_2 = (2**24) - 1
            self.test_val_sig_a_3 = (2**24) // 2
            self.test_val_sig_b_3 = (2**24) // 2
            self.test_val_sig_a_4 = 12582912
            self.test_val_sig_b_4 = 12550144
            self.test_val_sig_a_5 = 16744448
            self.test_val_sig_b_5 = 12615680
            self.test_val_sig_a_6 = 8421376
            self.test_val_sig_b_6 = 8421376

    def test_manual(self):
        params = FPUParams(sig_width=24, exp_width=8)
        help_values = TestLZA.HelpValues(params)
        lza = TestLZA.LZAModuleTest(params)

        def clz(sig_a, sig_b, carry):
            zeros = 0
            msb_bit_mask = 1 << (params.sig_width - 1)
            sum = sig_a + sig_b + carry
            while 1:
                if not (sum & msb_bit_mask):
                    zeros += 1
                    sum = sum << 1
                else:
                    return zeros

        def random_test():
            xor_mask = (2**params.sig_width) - 1
            sig_a = randint(1 << (params.sig_width - 1), (2**params.sig_width) - 1)
            sig_b = randint(1 << (params.sig_width - 1), sig_a)
            sig_b = (sig_b ^ xor_mask) | (1 << params.sig_width)
            resp = yield from lza.predict_request_adapter.call({"sig_a": sig_a, "sig_b": sig_b, "carry": 0})
            pred_lz = resp["shift_amount"]
            true_lz = clz(sig_a, sig_b, 0)
            assert pred_lz == true_lz or (pred_lz + 1) == true_lz

        def lza_test():
            test_cases = [
                {
                    "sig_a": help_values.test_val_sig_a_1,
                    "sig_b": help_values.test_val_sig_b_1,
                    "carry": 0,
                },
                {
                    "sig_a": help_values.test_val_sig_a_1,
                    "sig_b": help_values.test_val_sig_b_1,
                    "carry": 1,
                },
                {
                    "sig_a": help_values.test_val_sig_a_2,
                    "sig_b": help_values.test_val_sig_b_2,
                    "carry": 0,
                },
                {
                    "sig_a": help_values.test_val_sig_a_2,
                    "sig_b": help_values.test_val_sig_b_2,
                    "carry": 1,
                },
                {
                    "sig_a": help_values.test_val_sig_a_3,
                    "sig_b": help_values.test_val_sig_b_3,
                    "carry": 0,
                },
                {
                    "sig_a": help_values.test_val_sig_a_3,
                    "sig_b": help_values.test_val_sig_b_3,
                    "carry": 1,
                },
                {
                    "sig_a": help_values.test_val_sig_a_4,
                    "sig_b": help_values.test_val_sig_b_4,
                    "carry": 0,
                },
                {
                    "sig_a": help_values.test_val_sig_a_4,
                    "sig_b": help_values.test_val_sig_b_4,
                    "carry": 1,
                },
                {
                    "sig_a": help_values.test_val_sig_a_5,
                    "sig_b": help_values.test_val_sig_b_5,
                    "carry": 1,
                },
                {
                    "sig_a": help_values.test_val_sig_a_5,
                    "sig_b": help_values.test_val_sig_b_5,
                    "carry": 1,
                },
                {
                    "sig_a": help_values.test_val_sig_a_6,
                    "sig_b": help_values.test_val_sig_b_6,
                    "carry": 0,
                },
                {
                    "sig_a": help_values.test_val_sig_a_6,
                    "sig_b": help_values.test_val_sig_b_6,
                    "carry": 1,
                },
            ]
            expected_results = [
                {"shift_amount": 13, "is_zero": 0},
                {"shift_amount": 13, "is_zero": 0},
                {"shift_amount": 23, "is_zero": 0},
                {"shift_amount": 0, "is_zero": 1},
                {"shift_amount": 0, "is_zero": 0},
                {"shift_amount": 23, "is_zero": 0},
                {"shift_amount": 0, "is_zero": 0},
                {"shift_amount": 0, "is_zero": 0},
                {"shift_amount": 0, "is_zero": 0},
                {"shift_amount": 0, "is_zero": 0},
                {"shift_amount": 7, "is_zero": 0},
                {"shift_amount": 7, "is_zero": 0},
            ]
            for i in range(len(test_cases)):
                resp = yield from lza.predict_request_adapter.call(test_cases[i])
                assert resp["shift_amount"] == expected_results[i]["shift_amount"]
                assert resp["is_zero"] == expected_results[i]["is_zero"]

        def test_process():
            yield from lza_test()
            yield from random_test()

        with self.run_simulation(lza) as sim:
            sim.add_process(test_process)