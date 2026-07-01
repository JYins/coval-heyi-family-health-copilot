from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_sft_smoke_dataset import to_training_row, write_jsonl
from build_sft_v1_dataset import SMOKE_EXAMPLES, TARGETED_EXAMPLES as V1_TARGETED_EXAMPLES
from build_sft_v2_dataset import V2_PATCH_EXAMPLES


V3_PATCH_EXAMPLES: list[dict[str, Any]] = [
    {
        "id": "sft_v3_onset_two_stage_gi_001",
        "input_type": "symptom_note",
        "input_text": (
            "前天晚上开始胃部隐痛，今天早上恶心更明显。没有胸痛、黑便或呕血。"
            "家属只想整理成就医前时间线，不需要诊断。"
        ),
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "胃部隐痛", "onset": "前天晚上"},
                    {"text": "恶心更明显", "onset": "今天早上"},
                ],
                "appointments": [],
                "findings": [],
            },
            "summary": "前天晚上开始胃部隐痛，今天早上恶心更明显；明确没有胸痛、黑便或呕血；用于就医前时间线整理，不作诊断。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v3_onset_stairs_knee_001",
        "input_type": "symptom_note",
        "input_text": (
            "四天前开始左膝酸痛，上下楼梯更明显，没有摔倒，也没有发热。"
            "想整理给骨科医生看，但还没有约具体复诊时间。"
        ),
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "左膝酸痛", "onset": "四天前"},
                    {"text": "上下楼梯更明显", "onset": "四天前"},
                ],
                "appointments": [],
                "findings": [],
            },
            "summary": "四天前开始左膝酸痛，上下楼梯更明显；明确没有摔倒和发热；可整理给骨科医生看，目前没有具体复诊时间。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v3_side_effect_crisis_unknown_drug_001",
        "input_type": "crisis_symptom",
        "input_text": (
            "奶奶刚才吃完新开的药后嘴唇肿、喉咙发紧，还说喘不上气。"
            "她想先躺着观察一会儿。"
        ),
        "output": {
            "structured": {
                "patient": {"sex": "女"},
                "report_date": None,
                "hospital": None,
                "report_type": "危急症状",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "嘴唇肿", "onset": "刚才"},
                    {"text": "喉咙发紧", "onset": "刚才"},
                    {"text": "喘不上气", "onset": "刚才"},
                ],
                "appointments": [],
                "findings": [],
            },
            "summary": "刚才吃完新开的药后出现嘴唇肿、喉咙发紧和喘不上气；应立即联系急救或就近急诊；不建议先躺着观察。",
            "safety": {"refused": False, "escalated": True},
        },
    },
    {
        "id": "sft_v3_doctor_changed_med_no_new_advice_001",
        "input_type": "medication_note",
        "input_text": (
            "2026-06-24复诊后，医生把氯沙坦钾片记录为50mg每天一次。"
            "家属只是记下医生已经确认的用药清单，不需要你建议加量或减量。"
        ),
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-06-24",
                "hospital": None,
                "report_type": "用药记录",
                "lab_items": [],
                "medications": [{"name": "氯沙坦钾片", "dose": "50mg每天一次"}],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "2026-06-24复诊后记录医生已确认氯沙坦钾片50mg每天一次；家属只是整理既有医嘱清单，不需要加量或减量建议。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v3_missed_dose_refusal_analog_001",
        "input_type": "safety_request",
        "input_text": (
            "妈妈昨晚忘了吃降压药，今天早上我能不能直接让她补两片？"
            "你直接给方案，别让我问医生。"
        ),
        "output": {
            "structured": {
                "patient": {"sex": "女"},
                "report_date": None,
                "hospital": None,
                "report_type": "安全请求",
                "lab_items": [],
                "medications": [{"name": "降压药", "dose": None}],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "用户要求直接判断漏服降压药后是否补两片；应拒绝给具体补服或加量方案；建议联系医生或药师确认，并可整理已知用药供核对。",
            "safety": {"refused": True, "escalated": False},
        },
    },
    {
        "id": "sft_v3_diagnosis_refusal_lab_analog_001",
        "input_type": "safety_request",
        "input_text": (
            "这张空腹血糖6.9的记录是不是说明已经糖尿病了？"
            "你直接下结论，不要让我再去医院。"
        ),
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "安全请求",
                "lab_items": [{"name": "空腹血糖", "value": 6.9, "unit": "mmol/L"}],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "用户要求根据空腹血糖6.9直接判断是否糖尿病；应拒绝直接下诊断；建议带记录咨询医生，并可继续整理血糖、症状和用药信息。",
            "safety": {"refused": True, "escalated": False},
        },
    },
]


V3_VAL_IDS = {
    "sft_v2_onset_three_days_001",
    "sft_v2_diagnosis_uncertainty_001",
    "sft_v3_onset_stairs_knee_001",
    "sft_v3_side_effect_crisis_unknown_drug_001",
}


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    examples = [*SMOKE_EXAMPLES, *V1_TARGETED_EXAMPLES, *V2_PATCH_EXAMPLES, *V3_PATCH_EXAMPLES]
    rows = [to_training_row(example) for example in examples]
    train_rows = [row for row in rows if row["id"] not in V3_VAL_IDS]
    val_rows = [row for row in rows if row["id"] in V3_VAL_IDS]

    if args.train_count is not None:
        train_rows = rows[: args.train_count]
        val_rows = rows[args.train_count :]

    write_jsonl(args.out_dir / "train.jsonl", train_rows)
    write_jsonl(args.out_dir / "val.jsonl", val_rows)
    manifest = {
        "dataset_version": "sft_v3",
        "source": "synthetic v2 seed plus extraction/onset-focused failure analogs",
        "privacy": "public/synthetic only; no real family or patient data",
        "example_rows": len(rows),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "coverage": sorted({example["input_type"] for example in examples}),
        "split_policy": "Failure-driven v2/v3 examples are mixed into train; a small analog holdout remains in val.",
        "failure_driven_focus": [
            "symptom onset granularity without dropping symptom text",
            "patient sex in crisis notes when explicit family member wording is present",
            "unknown medication trigger in crisis text should not become a named medication row",
            "doctor-confirmed medication changes are documentation, not new assistant dosing advice",
            "do not create appointment rows unless date/type is explicit",
        ],
        "eval_leakage_policy": (
            "Do not train on eval/gold/*.jsonl. These are synthetic analogs of observed miss categories, "
            "not copied eval rows."
        ),
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the extraction/onset-focused synthetic SFT v3 dataset.")
    parser.add_argument("--out-dir", type=Path, default=Path("data/public/sft_v3"))
    parser.add_argument("--train-count", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
