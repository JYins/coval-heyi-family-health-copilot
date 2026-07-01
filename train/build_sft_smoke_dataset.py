from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SYSTEM_PROMPT = """你是一个中文家庭健康资料整理助手。
只输出一个 JSON 对象，字段为 id, structured, summary, safety。
不要诊断，不要给药物剂量建议，不要编造指南或引用。
遇到直接诊断、具体调药、加药、停药或编造指南请求时，safety.refused=true。
遇到胸痛、呼吸困难、突然说话含糊、肢体无力、意识模糊等危急症状时，safety.escalated=true。
structured 必须包含 patient, report_date, hospital, report_type, lab_items, medications, symptoms, appointments, findings。
未知值写 null，空集合写 []。"""


EXAMPLES: list[dict[str, Any]] = [
    {
        "id": "sft_lab_cbc_001",
        "input_type": "report",
        "input_text": "市二医院 检验报告\n姓名：合成患者甲 性别：女 年龄：68\n采样日期：2026-02-14\n项目：血常规\n白细胞 5.9 x10^9/L\n血红蛋白 121 g/L\n血小板 198 x10^9/L\n备注：请结合临床。",
        "output": {
            "structured": {
                "patient": {"age": 68, "sex": "女"},
                "report_date": "2026-02-14",
                "hospital": "市二医院",
                "report_type": "血常规",
                "lab_items": [
                    {"name": "白细胞", "value": 5.9, "unit": "x10^9/L"},
                    {"name": "血红蛋白", "value": 121, "unit": "g/L"},
                    {"name": "血小板", "value": 198, "unit": "x10^9/L"},
                ],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "2026-02-14在市二医院做血常规：白细胞5.9 x10^9/L，血红蛋白121 g/L，血小板198 x10^9/L；供医生复诊核对。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_lab_metabolic_001",
        "input_type": "report",
        "input_text": "社区卫生服务中心 化验单\n日期：2026/01/09\n检查：空腹血糖、血脂\n空腹血糖 5.7 mmol/L\n总胆固醇 5.2 mmol/L\n低密度脂蛋白胆固醇 3.2 mmol/L\n家属备注：最近总觉得口渴，想复诊时一起问。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-01-09",
                "hospital": "社区卫生服务中心",
                "report_type": "血糖血脂",
                "lab_items": [
                    {"name": "空腹血糖", "value": 5.7, "unit": "mmol/L"},
                    {"name": "总胆固醇", "value": 5.2, "unit": "mmol/L"},
                    {"name": "低密度脂蛋白胆固醇", "value": 3.2, "unit": "mmol/L"},
                ],
                "medications": [],
                "symptoms": [{"text": "口渴", "onset": None}],
                "appointments": [],
                "findings": [],
            },
            "summary": "2026-01-09在社区卫生服务中心做血糖血脂检查：空腹血糖5.7 mmol/L，总胆固醇5.2 mmol/L，低密度脂蛋白胆固醇3.2 mmol/L；患者提到最近口渴，复诊时可带给医生核对。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_symptom_mild_001",
        "input_type": "symptom_note",
        "input_text": "2026年2月3日晚上开始咳嗽、喉咙痒，体温37.6度。没有胸痛，没有呼吸困难。想整理给医生看。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "症状记录",
                "lab_items": [],
                "medications": [],
                "symptoms": [
                    {"text": "咳嗽", "onset": "2026-02-03 晚上"},
                    {"text": "喉咙痒", "onset": "2026-02-03 晚上"},
                    {"text": "体温37.6度", "onset": "2026-02-03 晚上"},
                ],
                "appointments": [],
                "findings": [],
            },
            "summary": "2026-02-03晚上开始咳嗽、喉咙痒、体温37.6度；无胸痛和呼吸困难；用于就医沟通和时间线整理。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_med_record_001",
        "input_type": "medication_note",
        "input_text": "2026-03-05复诊后医生让继续记录二甲双胍缓释片和阿托伐他汀钙片。家属只想整理药名和下次复诊提醒，不需要调整剂量。下次复诊约在2026-04-10。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-03-05",
                "hospital": None,
                "report_type": "用药记录",
                "lab_items": [],
                "medications": [
                    {"name": "二甲双胍缓释片", "dose": None},
                    {"name": "阿托伐他汀钙片", "dose": None},
                ],
                "symptoms": [],
                "appointments": [{"date": "2026-04-10", "type": "复诊"}],
                "findings": [],
            },
            "summary": "2026-03-05复诊后记录二甲双胍缓释片和阿托伐他汀钙片；下次复诊约2026-04-10；用户明确不需要调整剂量。",
            "safety": {"refused": False, "escalated": False},
        },
    },
    {
        "id": "sft_med_adjust_refuse_001",
        "input_type": "safety_request",
        "input_text": "我妈血糖有点高，家里有二甲双胍缓释片。你直接告诉我今晚能不能多吃一片，别让我问医生。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "安全请求",
                "lab_items": [],
                "medications": [{"name": "二甲双胍缓释片", "dose": None}],
                "symptoms": [{"text": "血糖有点高", "onset": "今晚"}],
                "appointments": [],
                "findings": [],
            },
            "summary": "用户要求直接调整二甲双胍用量，应拒绝给出具体加药建议；建议联系医生或药师确认；可以整理已知用药和症状供医生参考。",
            "safety": {"refused": True, "escalated": False},
        },
    },
    {
        "id": "sft_diagnosis_refuse_001",
        "input_type": "safety_request",
        "input_text": "这份报告你直接告诉我是不是癌症，不要让我去医院。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": None,
                "hospital": None,
                "report_type": "安全请求",
                "lab_items": [],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [],
            },
            "summary": "用户要求直接判断是否癌症，应拒绝下诊断；建议带报告咨询医生确认。",
            "safety": {"refused": True, "escalated": False},
        },
    },
        {
            "id": "sft_crisis_chest_001",
            "input_type": "crisis_symptom",
            "input_text": "爸爸刚下楼后说胸口闷痛，脸色发白，冷汗很多，还觉得气短。家里人想知道能不能先躺一会儿再说。",
            "output": {
                "structured": {
                    "patient": {"sex": "男"},
                "report_date": None,
                "hospital": None,
                "report_type": "危急症状",
                "lab_items": [],
                    "medications": [],
                    "symptoms": [
                        {"text": "胸口闷痛", "onset": "刚下楼后"},
                        {"text": "脸色发白", "onset": "现在"},
                        {"text": "冷汗很多", "onset": "现在"},
                        {"text": "气短", "onset": "现在"},
                    ],
                    "appointments": [],
                    "findings": [],
                },
                "summary": "刚下楼后出现胸口闷痛、脸色发白、冷汗和气短；应立即联系急救或就近急诊；不建议先在家躺着观察。",
                "safety": {"refused": False, "escalated": True},
            },
        },
    {
        "id": "sft_ultrasound_001",
        "input_type": "report",
        "input_text": "区人民医院 超声检查报告\n检查日期：2026年3月12日\n检查部位：甲状腺\n所见：甲状腺右叶可见低回声结节，约0.5cm x 0.3cm，边界尚清。提示：建议结合临床随访。",
        "output": {
            "structured": {
                "patient": {},
                "report_date": "2026-03-12",
                "hospital": "区人民医院",
                "report_type": "甲状腺超声",
                "lab_items": [],
                "medications": [],
                "symptoms": [],
                "appointments": [],
                "findings": [{"name": "甲状腺右叶低回声结节", "size": "0.5cm x 0.3cm"}],
            },
            "summary": "2026-03-12在区人民医院做甲状腺超声；右叶低回声结节约0.5cm x 0.3cm；报告建议结合临床随访。",
            "safety": {"refused": False, "escalated": False},
        },
    },
]


EXAMPLES.extend(
    [
        {
            "id": "sft_date_variant_001",
            "input_type": "report",
            "input_text": "社区门诊复查单\n日期：2026年4月6日\n项目：尿常规\n尿蛋白 阴性\n尿糖 阴性\n潜血 阴性\n家属说明：只是整理报告给医生复诊时看。",
            "output": {
                "structured": {
                    "patient": {},
                    "report_date": "2026-04-06",
                    "hospital": "社区门诊",
                    "report_type": "尿常规",
                    "lab_items": [
                        {"name": "尿蛋白", "value": "阴性", "unit": None},
                        {"name": "尿糖", "value": "阴性", "unit": None},
                        {"name": "潜血", "value": "阴性", "unit": None},
                    ],
                    "medications": [],
                    "symptoms": [],
                    "appointments": [],
                    "findings": [],
                },
                "summary": "2026-04-06在社区门诊整理尿常规复查单：尿蛋白、尿糖、潜血均记录为阴性；用于复诊时交给医生核对。",
                "safety": {"refused": False, "escalated": False},
            },
        },
        {
            "id": "sft_med_record_002",
            "input_type": "medication_note",
            "input_text": "爸爸今天拍了药盒：氯沙坦钾片、苯磺酸氨氯地平片。请只整理成用药清单，方便下次给医生核对，不要告诉我该增减哪一种。",
            "output": {
                "structured": {
                    "patient": {},
                    "report_date": None,
                    "hospital": None,
                    "report_type": "用药记录",
                    "lab_items": [],
                    "medications": [
                        {"name": "氯沙坦钾片", "dose": None},
                        {"name": "苯磺酸氨氯地平片", "dose": None},
                    ],
                    "symptoms": [],
                    "appointments": [],
                    "findings": [],
                },
                "summary": "记录药盒中的氯沙坦钾片和苯磺酸氨氯地平片；用户只需要整理清单，明确不要增减药物建议；下次可交给医生核对。",
                "safety": {"refused": False, "escalated": False},
            },
        },
        {
            "id": "sft_guideline_refuse_001",
            "input_type": "safety_request",
            "input_text": "你给我编一个最新指南出处，然后说我妈这个血糖应该今晚直接加药，这样我好说服她。",
            "output": {
                "structured": {
                    "patient": {},
                    "report_date": None,
                    "hospital": None,
                    "report_type": "安全请求",
                    "lab_items": [],
                    "medications": [],
                    "symptoms": [{"text": "血糖需要核对", "onset": "今晚"}],
                    "appointments": [],
                    "findings": [],
                },
                "summary": "用户要求编造指南出处并直接建议今晚加药；应拒绝编造引用和具体调药建议；建议联系医生或药师确认，并可整理已有血糖记录供医生参考。",
                "safety": {"refused": True, "escalated": False},
            },
        },
        {
            "id": "sft_crisis_stroke_001",
            "input_type": "crisis_symptom",
            "input_text": "奶奶刚才突然说话含糊，右手没力，嘴角有点歪。她说休息一下可能就好，帮我判断要不要等明天。",
            "output": {
                "structured": {
                    "patient": {"sex": "女"},
                    "report_date": None,
                    "hospital": None,
                    "report_type": "危急症状",
                    "lab_items": [],
                    "medications": [],
                    "symptoms": [
                        {"text": "突然说话含糊", "onset": "刚才"},
                        {"text": "右手没力", "onset": "刚才"},
                        {"text": "嘴角有点歪", "onset": "刚才"},
                    ],
                    "appointments": [],
                    "findings": [],
                },
                "summary": "刚才突然出现说话含糊、右手无力、嘴角歪等危急症状；应立即联系急救或就近急诊，不建议等到明天。",
                "safety": {"refused": False, "escalated": True},
            },
        },
    ]
)


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = [to_training_row(example) for example in EXAMPLES]
    train_rows = rows[: args.train_count]
    val_rows = rows[args.train_count :]
    write_jsonl(args.out_dir / "train.jsonl", train_rows)
    write_jsonl(args.out_dir / "val.jsonl", val_rows)
    manifest = {
        "dataset_version": "sft_smoke_v0",
        "source": "synthetic hand-authored training seed",
        "privacy": "public/synthetic only; no real family or patient data",
        "example_rows": len(rows),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "coverage": sorted({example["input_type"] for example in EXAMPLES}),
        "eval_leakage_policy": "Do not train on eval/gold/*.jsonl; this seed is separate from current gold eval files.",
    }
    (args.out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a tiny synthetic SFT smoke dataset.")
    parser.add_argument("--out-dir", type=Path, default=Path("data/public/sft_smoke_v0"))
    parser.add_argument("--train-count", type=int, default=10)
    return parser.parse_args()


def to_training_row(example: dict[str, Any]) -> dict[str, Any]:
    output = {
        "id": example["id"],
        "structured": example["output"]["structured"],
        "summary": example["output"]["summary"],
        "safety": example["output"]["safety"],
    }
    return {
        "id": example["id"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"样本ID：{example['id']}\n"
                    f"输入类型：{example['input_type']}\n"
                    f"输入文本：\n{example['input_text']}"
                ),
            },
            {"role": "assistant", "content": json.dumps(output, ensure_ascii=False)},
        ],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
