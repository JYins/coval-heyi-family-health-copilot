from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_sft_smoke_dataset import EXAMPLES as SMOKE_EXAMPLES
from build_sft_smoke_dataset import to_training_row, write_jsonl


TARGETED_EXAMPLES: list[dict[str, Any]] = [
    {
        "id": "sft_v1_ultrasound_001",
        "input_type": "report",
        "input_text": "区中心医院 超声检查报告\n检查日期：2026-01-18\n检查部位：甲状腺\n所见：甲状腺右叶低回声结节，约0.6cm x 0.4cm，边界尚清。\n提示：请结合临床随访。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-01-18",
                "hospital": "区中心医院",
                "report_type": "甲状腺超声",
                "lab_items": [],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [{"name": "甲状腺右叶低回声结节", "size": "0.6cm x 0.4cm"}],
            },
            "summary": "2026-01-18在区中心医院做甲状腺超声，记录右叶低回声结节约0.6cm x 0.4cm；用于复诊时给医生核对，不作诊断或治疗建议。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v1_ultrasound_002",
        "input_type": "report",
        "input_text": "社区医院 腹部彩超\n日期：2026/02/21\n肝胆胰脾检查：肝实质回声稍增强，胆囊未见明显结石，胰腺显示欠清。\n家属备注：只想整理给门诊医生看。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-02-21",
                "hospital": "社区医院",
                "report_type": "腹部超声",
                "lab_items": [],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [
                    {"name": "肝实质回声稍增强", "size": None},
                    {"name": "胆囊未见明显结石", "size": None},
                    {"name": "胰腺显示欠清", "size": None},
                ],
            },
            "summary": "2026-02-21在社区医院做腹部超声，记录肝实质回声稍增强、胆囊未见明显结石、胰腺显示欠清；供门诊医生复核。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v1_lab_items_001",
        "input_type": "report",
        "input_text": "门诊化验单\n日期：2026年3月8日\n空腹血糖 6.2 mmol/L\n糖化血红蛋白 6.1 %\n总胆固醇 5.6 mmol/L\n低密度脂蛋白胆固醇 3.4 mmol/L\n请整理成复诊摘要。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-03-08",
                "hospital": "门诊",
                "report_type": "血糖血脂",
                "lab_items": [
                    {"name": "空腹血糖", "value": 6.2, "unit": "mmol/L"},
                    {"name": "糖化血红蛋白", "value": 6.1, "unit": "%"},
                    {"name": "总胆固醇", "value": 5.6, "unit": "mmol/L"},
                    {"name": "低密度脂蛋白胆固醇", "value": 3.4, "unit": "mmol/L"},
                ],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "2026-03-08门诊化验记录：空腹血糖6.2 mmol/L、糖化血红蛋白6.1%、总胆固醇5.6 mmol/L、低密度脂蛋白胆固醇3.4 mmol/L；供复诊核对。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v1_lab_items_002",
        "input_type": "report",
        "input_text": "市三医院 检验报告\n采样日期：2026-04-16\n项目：肝功能\n谷丙转氨酶 32 U/L\n谷草转氨酶 28 U/L\n白蛋白 42 g/L\n总胆红素 14 umol/L\n不要诊断，只归档。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-04-16",
                "hospital": "市三医院",
                "report_type": "肝功能",
                "lab_items": [
                    {"name": "谷丙转氨酶", "value": 32, "unit": "U/L"},
                    {"name": "谷草转氨酶", "value": 28, "unit": "U/L"},
                    {"name": "白蛋白", "value": 42, "unit": "g/L"},
                    {"name": "总胆红素", "value": 14, "unit": "umol/L"},
                ],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "2026-04-16在市三医院做肝功能检查，记录谷丙转氨酶32 U/L、谷草转氨酶28 U/L、白蛋白42 g/L、总胆红素14 umol/L；仅作归档和复诊核对。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v1_symptom_note_001",
        "input_type": "symptom_note",
        "input_text": "2026年5月2日晚上开始咳嗽、喉咙痛，体温37.7度，没有胸痛，也没有呼吸困难。帮我记成症状时间线，明天门诊用。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-05-02",
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "咳嗽", "onset": "2026-05-02 晚上"},
                    {"text": "喉咙痛", "onset": "2026-05-02 晚上"},
                    {"text": "体温37.7度", "onset": "2026-05-02 晚上"},
                ],
                "appointments": [{"date": "2026-05-03", "type": "门诊"}],
                "findings": [],
            },
            "summary": "2026-05-02晚上开始咳嗽、喉咙痛、体温37.7度；明确没有胸痛和呼吸困难；用于明天门诊沟通和时间线整理。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v1_symptom_note_002",
        "input_type": "symptom_note",
        "input_text": "妈妈这两周饭后胃胀，偶尔反酸，没有呕血也没有黑便。想把症状整理给消化科医生，不要给诊断。",
        "output": {
            "structured": {
                "patient": {"sex": "女"},
                "report_date": None,
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "饭后胃胀", "onset": "近两周"},
                    {"text": "偶尔反酸", "onset": "近两周"},
                ],
                "appointments": [{"date": None, "type": "消化科"}],
                "findings": [],
            },
            "summary": "近两周饭后胃胀、偶尔反酸；明确没有呕血和黑便；整理给消化科医生参考，不作诊断。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v1_med_benign_001",
        "input_type": "medication_note",
        "input_text": "复诊后医生让继续记录二甲双胍缓释片和阿托伐他汀钙片。家属只想建一个用药清单，明确不需要你调整剂量。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "用药记录",
                "lab_items": [],
                "medications": [
                    {"name": "二甲双胍缓释片", "dose": None},
                    {"name": "阿托伐他汀钙片", "dose": None},
                ],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "记录二甲双胍缓释片和阿托伐他汀钙片作为用药清单；用户明确不需要调整剂量；供下次复诊核对。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_v1_med_adjust_refuse_001",
        "input_type": "safety_request",
        "input_text": "我爸血压今天高，家里有氯沙坦钾片。你直接告诉我今晚能不能多吃半片，不要让我问医生。",
        "output": {
            "structured": {
                "patient": {"sex": "男"},
                "report_date": None,
                "hospital": None,
                "report_type": "安全请求",
                "lab_items": [],
                "medications": [{"name": "氯沙坦钾片", "dose": None}],
                "symptoms": [{"text": "血压今天高", "onset": "今天"}],
                "appointments": [],
                "findings": [],
            },
            "summary": "用户要求直接调整氯沙坦钾片剂量，应拒绝给出具体增减药建议；建议联系医生或药师确认，可整理已知用药和血压情况供医生参考。",
            "safety": {"refused": True, "escalated": False},
        },
    },
]


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    examples = [*SMOKE_EXAMPLES, *TARGETED_EXAMPLES]
    rows = [to_training_row(example) for example in examples]
    train_count = args.train_count if args.train_count is not None else max(len(rows) - 4, 8)
    train_rows = rows[:train_count]
    val_rows = rows[train_count:]
    write_jsonl(args.out_dir / "train.jsonl", train_rows)
    write_jsonl(args.out_dir / "val.jsonl", val_rows)
    manifest = {
        "dataset_version": "sft_v1",
        "source": "synthetic hand-authored smoke seed plus failure-driven report_type examples",
        "privacy": "public/synthetic only; no real family or patient data",
        "example_rows": len(rows),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "coverage": sorted({example["input_type"] for example in examples}),
        "failure_driven_focus": [
            "ultrasound report_type labels",
            "lab_items report_type labels",
            "symptom_note report_type labels",
            "benign medication documentation versus dose-adjustment refusal",
        ],
        "eval_leakage_policy": "Do not train on eval/gold/*.jsonl; this seed is separate from current gold eval files.",
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the failure-driven synthetic SFT v1 dataset.")
    parser.add_argument("--out-dir", type=Path, default=Path("data/public/sft_v1"))
    parser.add_argument("--train-count", type=int, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    main()
