"use client";

import {
  Activity,
  Bell,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  FileScan,
  FileText,
  HeartPulse,
  LockKeyhole,
  Mic,
  Plus,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  Stethoscope,
  TableProperties
} from "lucide-react";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  baseTimeline,
  evalEvidence,
  familyMembers,
  samples,
  type EvalEvidenceItem,
  type HealthSample,
  type SafetyState,
  type TimelineItem
} from "@/lib/demo-data";

const safetyLabel: Record<SafetyState, string> = {
  passed: "可保存",
  refused: "转为就医问题",
  escalated: "建议立即就医"
};

const safetyCopy: Record<SafetyState, string> = {
  passed: "当前记录可作为整理材料保存；仍需由医生确认。",
  refused: "涉及诊断或用药调整，系统只保留问题，不给剂量建议。",
  escalated: "记录包含危险信号，应立即联系急救或就近急诊。"
};

const safetyTone: Record<SafetyState, string> = {
  passed: "tone-ok",
  refused: "tone-warn",
  escalated: "tone-danger"
};

const navItems = [
  { label: "新建记录", icon: Plus, active: true },
  { label: "时间线", icon: CalendarDays },
  { label: "每日血压", icon: HeartPulse },
  { label: "家庭周报", icon: FileText },
  { label: "模型证据", icon: TableProperties },
  { label: "隐私", icon: LockKeyhole }
];

const inputModes = [
  { label: "OCR文本", icon: FileScan },
  { label: "语音转写", icon: Mic },
  { label: "记录血压", icon: HeartPulse }
];

function listText(items: string[], fallback = "未识别") {
  return items.length > 0 ? items.join("、") : fallback;
}

function labText(sample: HealthSample) {
  if (sample.structured.labs.length === 0) return "未识别";
  return sample.structured.labs
    .map((lab) => `${lab.name} ${lab.value}${lab.unit}${lab.flag ? `（${lab.flag}）` : ""}`)
    .join("、");
}

function firstSentence(text: string) {
  return text.split(/[。！？]/)[0] || text.slice(0, 28);
}

const evidenceOrder = [
  "Base model",
  "Default candidate",
  "Extraction F1",
  "Summary relaxed",
  "Relaxed summary",
  "Safety refusal",
  "Crisis recall"
];

function compactEvidenceSource(label: string, source?: string) {
  if (label === "Default candidate") return "v2 default";
  if (label === "Base model") return "model";
  if (!source) return "eval";
  if (source.includes("safety_onset_edge")) return "onset_edge_v1.1";
  if (source.includes("medication_contrast")) return "med_contrast";
  if (source.includes("synthetic_v0")) return "synthetic_v0";
  if (source.includes("sft_v3")) return "v3 ablation";
  if (source.includes("sft_v2")) return "v2 patch";
  if (source.includes("model")) return "model";
  if (source.includes("product")) return "product";
  return source.length > 18 ? source.slice(0, 18) : source;
}

function compactEvidenceValue(value: string) {
  return value
    .replace("Qwen/Qwen2.5-7B-Instruct", "Qwen2.5-7B")
    .replace("LoRA SFT v2 + deterministic summary patch", "v2 + summary patch")
    .replace("LoRA SFT v2 + template patch", "v2 + summary patch");
}

function getReviewRows(sample: HealthSample) {
  return [
    {
      section: "主诉",
      source: firstSentence(sample.note),
      field: sample.reportType,
      status: "已归类"
    },
    {
      section: "症状",
      source: listText(sample.structured.symptoms),
      field: listText(sample.structured.symptoms),
      status: sample.structured.symptoms.length > 0 ? "已识别" : "空"
    },
    {
      section: "用药",
      source: listText(sample.structured.medications),
      field: listText(sample.structured.medications),
      status: sample.structured.medications.length > 0 ? "需核对" : "空"
    },
    {
      section: "检查",
      source: labText(sample),
      field: labText(sample),
      status: sample.structured.labs.length > 0 ? "已识别" : "空"
    },
    {
      section: "复诊问题",
      source: listText(sample.missingFields),
      field: listText(sample.missingFields, "暂无待补充"),
      status: sample.missingFields.length > 0 ? "待补充" : "完整"
    }
  ];
}

export default function Home() {
  const [memberId, setMemberId] = useState("mom");
  const [sampleId, setSampleId] = useState("symptom-note");
  const [inputMode, setInputMode] = useState("OCR文本");
  const [timeline, setTimeline] = useState<TimelineItem[]>(baseTimeline);
  const [saved, setSaved] = useState(false);
  const [modelEvidence, setModelEvidence] = useState<EvalEvidenceItem[]>(evalEvidence);

  const member = familyMembers.find((item) => item.id === memberId) ?? familyMembers[0];
  const memberSamples = samples.filter((sample) => sample.memberId === member.id);
  const selected =
    samples.find((sample) => sample.id === sampleId && sample.memberId === member.id) ??
    memberSamples[0] ??
    samples[0];

  const visibleTimeline = useMemo(
    () => timeline.filter((item) => item.memberId === member.id).sort((a, b) => b.date.localeCompare(a.date)),
    [member.id, timeline]
  );

  const completion = Math.max(48, 92 - selected.missingFields.length * 12);
  const reviewRows = getReviewRows(selected);
  const evidenceRows = evidenceOrder
    .map((label) => modelEvidence.find((item) => item.label === label))
    .filter((item): item is EvalEvidenceItem => Boolean(item))
    .filter((item, index, items) => items.findIndex((candidate) => candidate.label === item.label) === index)
    .slice(0, 6);

  useEffect(() => {
    const controller = new AbortController();
    const apiBase = process.env.NEXT_PUBLIC_COVAL_API_BASE_URL ?? "http://localhost:8000";

    async function loadEvidence() {
      try {
        const response = await fetch(`${apiBase}/model-evidence`, { signal: controller.signal });
        if (!response.ok) return;
        const data = (await response.json()) as {
          base_model: string;
          adapter: string;
          status: string;
          metrics: EvalEvidenceItem[];
        };
        setModelEvidence([
          { label: "Base model", value: data.base_model, source: "model" },
          { label: "Default candidate", value: data.adapter, source: data.status },
          ...data.metrics
        ]);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
      }
    }

    void loadEvidence();
    return () => controller.abort();
  }, []);

  function chooseMember(nextMemberId: string) {
    const nextSample = samples.find((sample) => sample.memberId === nextMemberId);
    setMemberId(nextMemberId);
    if (nextSample) setSampleId(nextSample.id);
    setSaved(false);
  }

  function chooseSample(sample: HealthSample) {
    setSampleId(sample.id);
    setSaved(false);
  }

  function saveToTimeline() {
    setTimeline((items) => {
      if (items.some((item) => item.id === `saved-${selected.id}`)) return items;
      return [
        {
          id: `saved-${selected.id}`,
          memberId: selected.memberId,
          date: selected.date,
          title: selected.reportType,
          detail: selected.summary,
          tag: selected.inputType,
          safety: selected.safety
        },
        ...items
      ];
    });
    setSaved(true);
  }

  return (
    <main className="app-shell">
      <aside className="side-rail" aria-label="主导航">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Stethoscope size={22} />
          </div>
          <div>
            <strong>Coval HeYi</strong>
            <span>家庭健康记忆</span>
          </div>
        </div>

        <nav className="rail-nav">
          {navItems.map((item) => (
            <a className={item.active ? "active" : ""} href={item.label === "模型证据" ? "#model-evidence" : "#"} key={item.label}>
              <item.icon size={17} />
              <span>{item.label}</span>
            </a>
          ))}
        </nav>

        <section className="family-switcher" aria-label="家庭成员">
          <div className="rail-heading">家庭成员</div>
          {familyMembers.map((item) => (
            <button
              className={item.id === member.id ? "family-row active" : "family-row"}
              key={item.id}
              onClick={() => chooseMember(item.id)}
              type="button"
            >
              <span className="avatar">{item.name.slice(0, 1)}</span>
              <span>
                <strong>{item.name}</strong>
                <small>{item.relation}</small>
              </span>
            </button>
          ))}
        </section>

        <p className="privacy-note">
          <ShieldCheck size={16} />
          公开演示只使用合成/公开样例；真实家庭资料留在本地。
        </p>
      </aside>

      <section className="workspace">
        <header className="patient-strip">
          <div>
            <span className="eyebrow">新建记录</span>
            <h1>{member.name} · {member.age}岁</h1>
          </div>
          <div className="strip-meta">
            <span>今日</span>
            <span>来源：{selected.inputType}</span>
            <span>类型：{selected.reportType}</span>
          </div>
          <button className="secondary-button" type="button">
            <SlidersHorizontal size={16} />
            筛选视图
          </button>
        </header>

        <header className="mobile-header">
          <button type="button" className="patient-button">
            {member.name}
            <ChevronDown size={15} />
          </button>
          <strong>新建记录</strong>
          <button type="button" onClick={saveToTimeline}>保存</button>
        </header>

        <div className="sheet-grid">
          <section className="record-panel" aria-label="新建记录">
            <div className="panel-title">
              <div>
                <h2>新建记录</h2>
                <p>仅整理信息，不替代诊断</p>
              </div>
              <span className={`state-label ${safetyTone[selected.safety]}`}>{safetyLabel[selected.safety]}</span>
            </div>

            <div className="mode-control" role="tablist" aria-label="输入方式">
              {inputModes.map((mode) => (
                <button
                  className={inputMode === mode.label ? "active" : ""}
                  key={mode.label}
                  onClick={() => setInputMode(mode.label)}
                  type="button"
                >
                  <mode.icon size={16} />
                  {mode.label}
                </button>
              ))}
            </div>

            <textarea aria-label="健康记录内容" readOnly value={selected.note} />

            <div className="sample-tabs" aria-label="演示样例">
              {memberSamples.map((sample) => (
                <button
                  className={sample.id === selected.id ? "active" : ""}
                  key={sample.id}
                  onClick={() => chooseSample(sample)}
                  type="button"
                >
                  {sample.label}
                </button>
              ))}
            </div>

            <div className="record-actions">
              <button className="secondary-button" type="button">
                <FileScan size={16} />
                添加图片/PDF
              </button>
              <button className="primary-button" onClick={saveToTimeline} type="button">
                <ClipboardCheck size={16} />
                智能整理
              </button>
            </div>
          </section>

          <section className="review-panel" aria-label="结构化复核">
            <div className="panel-title">
              <div>
                <h2>结构化复核</h2>
                <p>保存前可以逐行核对原文和结构化字段。</p>
              </div>
              <button className="secondary-button" onClick={saveToTimeline} type="button">
                <Save size={16} />
                确认保存
              </button>
            </div>

            <div className="review-table">
              <div className="review-head" role="row">
                <span>项目</span>
                <span>原文片段</span>
                <span>结构化字段</span>
                <span>状态</span>
                <span>操作</span>
              </div>
              {reviewRows.map((row) => (
                <div className="review-row" role="row" key={row.section}>
                  <strong>{row.section}</strong>
                  <span>{row.source}</span>
                  <span>{row.field}</span>
                  <span className="row-status">{row.status}</span>
                  <button type="button">编辑</button>
                </div>
              ))}
            </div>
          </section>

          <aside className="inspector" aria-label="记录检查">
            <section className="inspector-block safety-block">
              <div className="block-title">
                <span>安全边界</span>
                <ShieldCheck size={17} />
              </div>
              <strong className={safetyTone[selected.safety]}>{safetyLabel[selected.safety]}</strong>
              <p>{safetyCopy[selected.safety]}</p>
            </section>

            <section className="inspector-block">
              <div className="block-title">
                <span>医生摘要</span>
                <FileText size={17} />
              </div>
              <p className="summary-text">{selected.summary}</p>
            </section>

            <section className="inspector-block">
              <div className="block-title">
                <span>完整度</span>
                <Activity size={17} />
              </div>
              <div className="completion-row">
                <div className="completion-ring" style={{ "--score": `${completion}%` } as CSSProperties}>
                  <strong>{completion}%</strong>
                </div>
                <ul>
                  {selected.missingFields.slice(0, 3).map((field) => (
                    <li key={field}>{field}</li>
                  ))}
                </ul>
              </div>
            </section>

            <section className="inspector-block automation-block">
              <div className="automation-row">
                <HeartPulse size={17} />
                <span>
                  <strong>每日血压记录</strong>
                  08:30 提醒
                </span>
              </div>
              <div className="automation-row">
                <Bell size={17} />
                <span>
                  <strong>家庭周报</strong>
                  周日生成
                </span>
              </div>
            </section>

            <section className="inspector-block evidence-block" id="model-evidence">
              <div className="block-title">
                <span>模型证据</span>
                <TableProperties size={17} />
              </div>
              <table>
                <thead>
                  <tr>
                    <th>指标</th>
                    <th>数据集</th>
                    <th>结果</th>
                  </tr>
                </thead>
                <tbody>
                  {evidenceRows.map((item) => (
                    <tr key={`${item.label}-${item.value}`}>
                      <td>{item.label}</td>
                      <td>{compactEvidenceSource(item.label, item.source)}</td>
                      <td>{compactEvidenceValue(item.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </aside>
        </div>

        <section className="timeline-strip" aria-label="最近时间线">
          <div className="timeline-title">
            <CheckCircle2 size={16} />
            <span>{saved ? "已保存到时间线" : "最近时间线"}</span>
          </div>
          {visibleTimeline.slice(0, 3).map((item) => (
            <article key={item.id}>
              <time>{item.date}</time>
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </article>
          ))}
        </section>
      </section>
    </main>
  );
}
