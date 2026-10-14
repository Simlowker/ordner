"""mlx_lm.lora on the pre-rendered distillation turns (see prepare.py): rows {"prompt_text", "completion_text"} are
tokenized raw (no chat template on top, no extra BOS: the text starts with <s>), loss on the completion only.
Run through train.sh (macstudio)."""
from mlx_lm.tuner import datasets as D

from ordner.finetune.train import log_memory, thinking_off


class RawTurns:
    def __init__(self, data, tokenizer):
        self._data, self.tokenizer = data, tokenizer

    def process(self, d):
        p = self.tokenizer.encode(d["prompt_text"], add_special_tokens=False)
        c = self.tokenizer.encode(d["completion_text"], add_special_tokens=False)
        return p + c, len(p)

    def __getitem__(self, i):
        return self._data[i]

    def __len__(self):
        return len(self._data)


_create = D.create_dataset


def create_dataset(data, tokenizer, config):
    if len(data) and "prompt_text" in data[0]:
        assert getattr(config, "mask_prompt", False), "mask_prompt must be true: loss on the assistant reply only"
        return RawTurns(data, tokenizer)
    return _create(data, tokenizer, config)


if __name__ == "__main__":
    from mlx_lm import lora

    D.create_dataset = create_dataset
    thinking_off()
    log_memory()
    lora.main()
