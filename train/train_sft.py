from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
from typing import Any


def main() -> None:
    args = parse_args()
    config = read_json(args.config)
    check_paths(args.train_jsonl, args.val_jsonl, args.output_dir)

    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    tokenizer = AutoTokenizer.from_pretrained(
        config["base_model"],
        cache_dir=config.get("cache_dir"),
        local_files_only=args.local_files_only,
        trust_remote_code=False,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config["base_model"],
        cache_dir=config.get("cache_dir"),
        local_files_only=args.local_files_only,
        trust_remote_code=False,
        torch_dtype="auto",
        device_map="auto",
    )

    dataset = load_dataset(
        "json",
        data_files={
            "train": str(args.train_jsonl),
            "validation": str(args.val_jsonl),
        },
    )

    def format_row(row: dict[str, Any]) -> str:
        return tokenizer.apply_chat_template(
            row["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )

    peft_config = LoraConfig(**config["lora"])
    train_cfg = config["train"]
    training_args, sft_arg_names = build_sft_config(SFTConfig, train_cfg, args.output_dir)
    trainer, trainer_arg_names = build_sft_trainer(
        SFTTrainer,
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        peft_config=peft_config,
        formatting_func=format_row,
        tokenizer=tokenizer,
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    write_run_manifest(args, config, sft_arg_names, trainer_arg_names)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small LoRA SFT smoke training job.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--train-jsonl", type=Path, required=True)
    parser.add_argument("--val-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be an object: {path}")
    return data


def check_paths(train_jsonl: Path, val_jsonl: Path, output_dir: Path) -> None:
    for path in [train_jsonl, val_jsonl]:
        if not path.exists():
            raise FileNotFoundError(f"Missing training file: {path}")
    output_text = str(output_dir).replace("\\", "/")
    if "/MEng_Project" in output_text:
        raise ValueError(f"Refusing thesis output path: {output_dir}")


def build_sft_config(sft_config_cls: Any, train_cfg: dict[str, Any], output_dir: Path) -> tuple[Any, dict[str, str]]:
    signature = inspect.signature(sft_config_cls.__init__)
    accepted = set(signature.parameters)
    kwargs: dict[str, Any] = {
        "output_dir": str(output_dir),
        "learning_rate": float(train_cfg["learning_rate"]),
        "per_device_train_batch_size": int(train_cfg["batch_size"]),
        "gradient_accumulation_steps": int(train_cfg["gradient_accumulation_steps"]),
        "num_train_epochs": float(train_cfg["epochs"]),
        "bf16": bool(train_cfg["bf16"]),
        "seed": int(train_cfg["seed"]),
        "logging_steps": 1,
        "save_strategy": "epoch",
        "report_to": [],
    }

    length_key = "max_length" if "max_length" in accepted else "max_seq_length"
    kwargs[length_key] = int(train_cfg["max_seq_length"])

    eval_key = "eval_strategy" if "eval_strategy" in accepted else "evaluation_strategy"
    kwargs[eval_key] = "epoch"

    filtered = {key: value for key, value in kwargs.items() if key in accepted}
    dropped = sorted(set(kwargs) - set(filtered))
    if dropped:
        print(f"SFTConfig does not accept these optional args, dropping: {dropped}")
    return sft_config_cls(**filtered), {"length_key": length_key, "eval_key": eval_key}


def build_sft_trainer(trainer_cls: Any, **kwargs: Any) -> tuple[Any, dict[str, str]]:
    signature = inspect.signature(trainer_cls.__init__)
    accepted = set(signature.parameters)
    tokenizer = kwargs.pop("tokenizer")
    if "processing_class" in accepted:
        kwargs["processing_class"] = tokenizer
        tokenizer_arg = "processing_class"
    elif "tokenizer" in accepted:
        kwargs["tokenizer"] = tokenizer
        tokenizer_arg = "tokenizer"
    else:
        raise TypeError("Installed SFTTrainer accepts neither processing_class nor tokenizer")

    filtered = {key: value for key, value in kwargs.items() if key in accepted}
    dropped = sorted(set(kwargs) - set(filtered))
    if dropped:
        print(f"SFTTrainer does not accept these optional args, dropping: {dropped}")
    return trainer_cls(**filtered), {"tokenizer_arg": tokenizer_arg}


def write_run_manifest(
    args: argparse.Namespace,
    config: dict[str, Any],
    sft_arg_names: dict[str, str],
    trainer_arg_names: dict[str, str],
) -> None:
    manifest = {
        "config": str(args.config),
        "train_jsonl": str(args.train_jsonl),
        "val_jsonl": str(args.val_jsonl),
        "output_dir": str(args.output_dir),
        "base_model": config["base_model"],
        "sft_config_arg_names": sft_arg_names,
        "sft_trainer_arg_names": trainer_arg_names,
        "privacy": "public/synthetic only; no real family or patient data",
    }
    path = args.output_dir / "sft_run_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
