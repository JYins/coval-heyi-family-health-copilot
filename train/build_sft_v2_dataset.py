from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_sft_smoke_dataset import to_training_row, write_jsonl
from build_sft_v1_dataset import TARGETED_EXAMPLES as V1_TARGETED_EXAMPLES
from build_sft_v1_dataset import SMOKE_EXAMPLES


V2_PATCH_EXAMPLES: list[dict[str, Any]] = [
    {
        "id": "sft_v2_med_doctor_changed_record_001",
        "input_type": "medication_note",
        "input_text": (
            "2026-06-19复诊后，医生把阿托伐他汀钙片调整为20mg每晚一次。"
            "家属只想把医生已经调整过的用药记录整理进清单，明确不需要你再给增减药建议。"
        ),
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-06-19",
                "hospital": None,
                "report_type": "用药记录",
                "lab_items": [],
                "medications": [{"name": "阿托伐他汀钙片", "dose": "20mg每晚一次"}],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": (
                "2026-06-19复诊后记录医生已将阿托伐他汀钙片调整为20mg每晚一次；"
                "这是医生已做出的用药记录，家属不需要调药建议；用于下次就医沟通和核对。"
            ),
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v2_missed_dose_refusal_001",
        "input_type": "safety_request",
        "input_text": (
            "爸爸早上漏服了一次缬沙坦，晚上想问能不能直接补两片，"
            "或者明天早上加倍吃，不想再问医生。"
        ),
        "output": {
            "structured": {
                "patient": {"sex": "男"},
                "report_date": None,
                "hospital": None,
                "report_type": "安全请求",
                "lab_items": [],
                "medications": [{"name": "缬沙坦", "dose": None}],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": (
                "用户要求直接判断漏服后是否补两片或加倍服用缬沙坦；"
                "应拒绝给具体补服或加量方案；建议按原医嘱或药品说明处理，并联系医生或药师确认。"
            ),
            "safety": {"refused": True, "escalated": False},
        },
    },
    {
        "id": "sft_v2_side_effect_crisis_001",
        "input_type": "crisis_symptom",
        "input_text": (
            "妈妈刚才吃完新开的药后嘴唇肿，喉咙发紧，还说喘不上气。"
            "她想先躺着观察一下。"
        ),
        "output": {
            "structured": {
                "patient": {"sex": "女"},
                "report_date": None,
                "hospital": None,
                "report_type": "危急症状",
                "lab_items": [],
                "medications": [{"name": "新开的药", "dose": None}],
                "symptoms": [
                    {"text": "嘴唇肿", "onset": "刚才"},
                    {"text": "喉咙发紧", "onset": "刚才"},
                    {"text": "喘不上气", "onset": "刚才"},
                ],
                "appointments": [],
                "findings": [],
            },
            "summary": (
                "刚才吃完新开的药后出现嘴唇肿、喉咙发紧和喘不上气；"
                "应立即联系急救或就近急诊；不建议先躺着观察。"
            ),
            "safety": {"refused": False, "escalated": True},
        },
    },
    {
        "id": "sft_v2_onset_last_night_001",
        "input_type": "symptom_note",
        "input_text": "昨晚开始胃部隐痛，今天早上有点恶心。没有胸痛、黑便或呕血。请整理成就医前摘要。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "胃部隐痛", "onset": "昨晚"},
                    {"text": "恶心", "onset": "今天早上"},
                ],
                "appointments": [],
                "findings": [],
            },
            "summary": (
                "昨晚开始胃部隐痛，今天早上有点恶心；明确没有胸痛、黑便或呕血；"
                "用于就医沟通和时间线整理。"
            ),
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v2_onset_three_days_001",
        "input_type": "symptom_note",
        "input_text": "三天前开始右膝酸痛，走楼梯更明显。没有摔倒，也没有发热。想整理给骨科门诊。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "右膝酸痛", "onset": "三天前"},
                    {"text": "走楼梯更明显", "onset": "三天前"},
                ],
                "appointments": [{"date": None, "type": "骨科门诊"}],
                "findings": [],
            },
            "summary": (
                "三天前开始右膝酸痛，走楼梯更明显；明确没有摔倒和发热；"
                "可整理给骨科门诊参考，不作诊断。"
            ),
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v2_diagnosis_uncertainty_001",
        "input_type": "safety_request",
        "input_text": "妈妈空腹血糖6.8，我想让你直接判断她是不是糖尿病，不要让我去问医生。",
        "output": {
            "structured": {
                "patient": {"sex": "女"},
                "report_date": None,
                "hospital": None,
                "report_type": "安全请求",
                "lab_items": [{"name": "空腹血糖", "value": 6.8, "unit": "mmol/L"}],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": (
                "用户要求根据空腹血糖记录直接判断是否糖尿病；应拒绝直接下诊断；"
                "建议带血糖记录咨询医生，并可整理既往血糖、症状和用药信息。"
            ),
            "safety": {"refused": True, "escalated": False},
        },
    },
]


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    examples = [*SMOKE_EXAMPLES, *V1_TARGETED_EXAMPLES, *V2_PATCH_EXAMPLES]
    rows = [to_training_row(example) for example in examples]
    train_count = args.train_count if args.train_count is not None else max(len(rows) - 6, 8)
    train_rows = rows[:train_count]
    val_rows = rows[train_count:]
    write_jsonl(args.out_dir / "train.jsonl", train_rows)
    write_jsonl(args.out_dir / "val.jsonl", val_rows)
    manifest = {
        "dataset_version": "sft_v2",
        "source": "synthetic hand-authored v1 seed plus failure-driven v1.1 hard-slice patch",
        "privacy": "public/synthetic only; no real family or patient data",
        "example_rows": len(rows),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "coverage": sorted({example["input_type"] for example in examples}),
        "failure_driven_focus": [
            "doctor-made medication-change records are documentation, not user dose advice",
            "missed-dose requests require refusal without losing medication name",
            "new-medication breathing/allergy symptoms require crisis escalation",
            "symptom onset granularity: 昨晚, 今天早上, 三天前, 刚才",
            "summary exactness for negated red flags and doctor-conversation prep",
        ],
        "eval_leakage_policy": (
            "Do not train on eval/gold/*.jsonl. These examples are synthetic analogs of observed failure shapes, "
            "not copied eval rows."
        ),
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the failure-driven synthetic SFT v2 dataset.")
    parser.add_argument("--out-dir", type=Path, default=Path("data/public/sft_v2"))
    parser.add_argument("--train-count", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
