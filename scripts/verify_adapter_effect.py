from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.inference import build_provider_from_env, outbound_network_guard
from src.inference.providers import TransformersAdapterProvider, _messages
from src.serve.api_schemas import StructuringRequest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify that the configured local PEFT adapter changes model logits."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("results/phase2_local_inference/adapter_effect.json"),
    )
    args = parser.parse_args()
    provider = build_provider_from_env()
    if (
        not isinstance(provider, TransformersAdapterProvider)
        or provider.describe().provider != "transformers_adapter"
    ):
        raise RuntimeError("COVAL_MODEL_PROVIDER must be transformers_adapter")

    payload = StructuringRequest(
        member_id="synthetic_adapter_probe",
        text="昨晚开始咳嗽，今天有点发热。只整理成复诊摘要，不作诊断。",
        input_mode="text",
    )
    with outbound_network_guard(allow_loopback=True):
        cold_load_ms = provider.start()
        result = compare_logits(provider, payload)

    report = {
        "schema_version": 1,
        "synthetic_only": True,
        "offline_simulation": {
            "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE"),
            "transformers_offline": os.environ.get("TRANSFORMERS_OFFLINE"),
            "python_socket_guard": "non_loopback_blocked",
            "physical_network_disconnected": False,
        },
        "provider": provider.describe().public_dict(),
        "cold_load_ms": round(cold_load_ms, 3),
        **result,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)
    print(json.dumps(result, ensure_ascii=False))


def compare_logits(
    provider: TransformersAdapterProvider,
    payload: StructuringRequest,
) -> dict[str, object]:
    import torch

    messages = _messages(payload, "adapter_effect_probe", "symptom_note")
    prompt = provider._tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    encoded = provider._tokenizer([prompt], return_tensors="pt")
    device = next(provider._model.parameters()).device
    encoded = {key: value.to(device) for key, value in encoded.items()}

    with torch.inference_mode():
        enabled = provider._model(**encoded).logits[:, -1, :].float().cpu()
        with provider._model.disable_adapter():
            disabled = provider._model(**encoded).logits[:, -1, :].float().cpu()

    delta = enabled - disabled
    max_abs = float(delta.abs().max().item())
    mean_abs = float(delta.abs().mean().item())
    l2 = float(torch.linalg.vector_norm(delta).item())
    if max_abs == 0.0:
        raise RuntimeError("adapter enable/disable produced identical logits")
    return {
        "adapter_changes_logits": True,
        "max_abs_logit_delta": max_abs,
        "mean_abs_logit_delta": mean_abs,
        "l2_logit_delta": l2,
        "enabled_argmax_token_id": int(enabled.argmax(dim=-1).item()),
        "disabled_argmax_token_id": int(disabled.argmax(dim=-1).item()),
    }


if __name__ == "__main__":
    main()
