"""mlx_lm.lora with the chat template rendered exactly as at extraction time (thinking disabled).

mlx-lm's TokenizerWrapper defaults enable_thinking to `has_thinking`, which is True for Apertus, so its chat
datasets would render "Deliberation: enabled" while extraction uses enable_thinking=False.
"""
import time

import mlx.core as mx
import mlx_lm.tokenizer_utils as tu
from mlx_lm import cli_ui


def thinking_off():
    tu.TokenizerWrapper.has_thinking = False


def log_memory():
    report, t0 = cli_ui.TrainUI.report_train, time.perf_counter()

    def report_train(self, it, *args):
        report(self, it, *args)
        print(f"  it {it}: peak {mx.get_peak_memory() / 1e9:.1f} GB, {time.perf_counter() - t0:.0f} s", flush=True)

    cli_ui.TrainUI.report_train = report_train


if __name__ == "__main__":
    from mlx_lm import lora

    thinking_off()
    log_memory()
    lora.main()
