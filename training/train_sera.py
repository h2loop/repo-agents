#!/usr/bin/env python3
"""
Fine-tune Nemotron-3-Nano-30B-A3B on the SERA OAI5G dataset using Megatron-Bridge.

This script loads the Nemotron-3-Nano SFT or PEFT (LoRA) recipe, overrides
the dataset config to use our chat-format SERA data with the patched chat
template (which adds {% generation %} markers for correct loss masking),
and launches training.

Usage (LoRA, 8× GPU single node):
    torchrun --nproc_per_node=8 training/train_sera.py \
        --peft lora \
        --seq-length 4096 \
        --config-file training/sera_overrides.yaml

Usage (full SFT, 8× GPU):
    torchrun --nproc_per_node=8 training/train_sera.py \
        --seq-length 4096 \
        --config-file training/sera_overrides.yaml

Additional CLI overrides (Hydra-style):
    torchrun --nproc_per_node=8 training/train_sera.py \
        --peft lora \
        --config-file training/sera_overrides.yaml \
        train.train_iters=2000 \
        optimizer.lr=2e-5
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Tuple

import torch
from omegaconf import OmegaConf

from megatron.bridge.data.builders.finetuning_dataset import FinetuningDatasetBuilder
from megatron.bridge.data.datasets.packed_sequence import PackedSequenceSpecs
from megatron.bridge.recipes.nemotronh.nemotron_3_nano import (
    nemotron_3_nano_peft_config,
    nemotron_3_nano_sft_config,
)
from megatron.bridge.training.config import ConfigContainer
from megatron.bridge.training.finetune import finetune
from megatron.bridge.training.gpt_step import forward_step
from megatron.bridge.training.utils.omegaconf_utils import (
    apply_overrides,
    create_omegaconf_dict_config,
    parse_hydra_overrides,
)

logger = logging.getLogger(__name__)

# Paths relative to repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
PATCHED_TEMPLATE = REPO_ROOT / "configs" / "nemotron_chat_template_patched.jinja"
DATA_DIR = REPO_ROOT / "data" / "megatron_sft"
TOOL_SCHEMAS = DATA_DIR / "tool_schemas.json"


def parse_cli_args() -> Tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Fine-tune Nemotron-3-Nano-30B on SERA dataset",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--config-file", type=str, default=None,
        help="Path to YAML override file (e.g., training/sera_overrides.yaml)",
    )
    parser.add_argument(
        "--peft", type=str, default=None, choices=["lora", "dora"],
        help="PEFT scheme (lora/dora). Omit for full SFT.",
    )
    parser.add_argument(
        "--seq-length", type=int, default=4096,
        help="Max sequence length (default: 4096)",
    )
    parser.add_argument(
        "--data-dir", type=str, default=None,
        help="Path to directory containing training.jsonl + validation.jsonl",
    )
    parser.add_argument(
        "--packed-sequence", action="store_true", default=True,
        help="Use sequence packing (default: True)",
    )
    parser.add_argument(
        "--no-packed-sequence", action="store_false", dest="packed_sequence",
        help="Disable sequence packing",
    )
    args, cli_overrides = parser.parse_known_args()
    return args, cli_overrides


def build_sera_dataset_config(
    data_dir: Path,
    seq_length: int,
    packed_sequence: bool,
) -> FinetuningDatasetBuilder:
    """Build dataset config pointing to our SERA JSONL data with chat template."""
    # Read patched chat template
    chat_template = PATCHED_TEMPLATE.read_text()

    # Read tool schemas
    import json
    tool_schemas = json.loads(TOOL_SCHEMAS.read_text())

    dataset_kwargs = {
        "chat": True,
        "use_hf_tokenizer_chat_template": True,
        "chat_template": chat_template,
        "tool_schemas": tool_schemas,
    }

    packed_specs = None
    if packed_sequence:
        packed_specs = PackedSequenceSpecs(
            packed_sequence_size=seq_length,
            pad_seq_to_mult=1,
        )

    return FinetuningDatasetBuilder(
        dataset_root=data_dir,
        tokenizer_model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
        seq_length=seq_length,
        seed=1234,
        packed_sequence_specs=packed_specs,
        dataset_kwargs=dataset_kwargs,
    )


def main() -> None:
    args, cli_overrides = parse_cli_args()

    # Pick recipe
    if args.peft:
        logger.info(f"Using PEFT recipe: {args.peft}")
        cfg: ConfigContainer = nemotron_3_nano_peft_config(peft_scheme=args.peft)
    else:
        logger.info("Using full SFT recipe")
        cfg = nemotron_3_nano_sft_config()

    # Override sequence length
    cfg.model.seq_length = args.seq_length
    cfg.dataset.seq_length = args.seq_length

    # Override dataset to use SERA data
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    cfg.dataset = build_sera_dataset_config(
        data_dir=data_dir,
        seq_length=args.seq_length,
        packed_sequence=args.packed_sequence,
    )

    # Merge YAML overrides
    merged_omega_conf, excluded_fields = create_omegaconf_dict_config(cfg)
    if args.config_file:
        if not os.path.exists(args.config_file):
            logger.error(f"Override YAML file not found: {args.config_file}")
            sys.exit(1)
        yaml_overrides = OmegaConf.load(args.config_file)
        merged_omega_conf = OmegaConf.merge(merged_omega_conf, yaml_overrides)

    # Apply CLI overrides
    if cli_overrides:
        merged_omega_conf = parse_hydra_overrides(merged_omega_conf, cli_overrides)

    # Apply back to config
    final_overrides = OmegaConf.to_container(merged_omega_conf, resolve=True)
    apply_overrides(cfg, final_overrides, excluded_fields)

    # Launch training
    finetune(config=cfg, forward_step_func=forward_step)

    if torch.distributed.is_initialized():
        torch.distributed.destroy_process_group()


if __name__ == "__main__":
    main()
