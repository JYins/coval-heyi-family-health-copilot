"use client";

import {
  Activity,
  Bell,
  CalendarDays,
  CheckCircle2,
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
  TableProperties
} from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  baseTimeline,
  evalEvidence,
  familyMembers,
  memorySteps,
  modeHints,
  samples,
  scopeFacts,
  type EvalEvidenceItem,
  type HealthSample,
  type SafetyState,
  type TimelineItem
} from "@/lib/demo-data";

const safetyLabel: Record<SafetyState, string> = {
  passed: "可整理，需确认",
  refused: "转为就医问题",
  escalated: "建议立即就医"
};

const safetyCopy: Record<SafetyState, string> = {
  passed: "当前记录可作为整理材料进入家庭记忆；医学判断仍需要医生确认。",
  refused: "涉及诊断或用药调整，系统只保留问题，不给剂量建议。",
  escalated: "记录包含危险信号，应立即联系急救或就近急诊。"
};

const safetyTone: Record<SafetyState, string> = {
  passed: "tone-ok",
  refused: "tone-warn",
  escalated: "tone-danger"
};

const navItems = [
  { label: "新建记录", icon: Plus, active: true, href: "#new-record" },
  { label: "健康记忆", icon: CalendarDays, href: "#timeline" },
  { label: "每日血压", icon: HeartPulse, href: "#new-record" },
  { label: "家庭周报", icon: FileText, href: "#weekly-report" },
  { label: "项目证据", icon: TableProperties, href: "#project-evidence" },
  { label: "隐私边界", icon: LockKeyhole, href: "#privacy-boundary" }
];

const inputModes = [
  { label: "OCR 文本", icon: FileScan },
  { label: "语音转写", icon: Mic },
  { label: "记录血压", icon: HeartPulse }
];

const evidenceOrder = [
  "Base model",
  "Default candidate",
  "Training data",
  "Extraction F1",
  "Safety refusal",
  "RAG phase"
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
  return text.split(/[。！？；]/)[0] || text.slice(0, 28);
}

function compactEvidenceSource(label: string, source?: string) {
  if (label === "Default candidate") return "v2 default";
  if (label === "Base model") return "model";
  if (label === "Training data") return "manifest";
  if (label === "RAG phase") return "phase 6";
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
    .replace("LoRA SFT v2 + template patch", "v2 + summary patch")
    .replace("LoRA SFT v2 + summary template", "v2 + summary patch");
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
  const [inputMode, setInputMode] = useState("OCR 文本");
  const [timeline, setTimeline] = useState<TimelineItem[]>(baseTimeline);
  const [saved, setSaved] = useState(false);
  const [organizedSampleId, setOrganizedSampleId] = useState<string | null>("symptom-note");
  const [checkedRows, setCheckedRows] = useState<Record<string, boolean>>({});
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

  const reviewRows = getReviewRows(selected);
  const isOrganized = organizedSampleId === selected.id;
  const intakeFacts = [
    { label: "来源", value: selected.source },
    { label: "日期", value: selected.date },
    { label: "待补", value: selected.missingFields.length > 0 ? `${selected.missingFields.length} 项` : "完整" }
  ];
  const visitPrepItems = [
    selected.structured.medications.length > 0
      ? `核对用药：${selected.structured.medications.slice(0, 2).join("、")}`
      : "带上近期用药清单",
    selected.structured.allergies.length > 0
      ? `过敏史：${selected.structured.allergies.slice(0, 2).join("、")}`
      : "确认过敏史",
    selected.missingFields[0] ? `补充：${selected.missingFields[0]}` : "摘要可用于复诊沟通"
  ];
  const checkedCount = reviewRows.filter((row) => checkedRows[`${selected.id}:${row.section}`]).length;
  const evidenceRows = evidenceOrder
    .map((label) => modelEvidence.find((item) => item.label === label))
    .filter((item): item is EvalEvidenceItem => Boolean(item))
    .filter((item, index, items) => items.findIndex((candidate) => candidate.label === item.label) === index)
    .slice(0, 6);

  useEffect(() => {
    const controller = new AbortController();
    const apiBase = process.env.NEXT_PUBLIC_COVAL_API_BASE_URL ?? "http://127.0.0.1:8000";

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
          { label: "Training data", value: "26 synthetic rows", source: "sft_v2 manifest" },
          ...data.metrics,
          { label: "RAG phase", value: "retrieval scaffold only", source: "rag_v0" }
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
    setOrganizedSampleId(null);
    setSaved(false);
  }

  function chooseSample(sample: HealthSample) {
    setSampleId(sample.id);
    setInputMode(sample.inputType === "手动记录" || sample.inputType === "安全请求" ? "OCR 文本" : sample.inputType);
    setOrganizedSampleId(null);
    setSaved(false);
  }

  function organizeRecord() {
    setOrganizedSampleId(selected.id);
    setSaved(false);
  }

  function toggleReviewCheck(section: string) {
    const key = `${selected.id}:${section}`;
    setCheckedRows((items) => ({ ...items, [key]: !items[key] }));
  }

  function saveToTimeline() {
    if (!isOrganized) return;
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
            <Image alt="" className="brand-mark-image" height={34} priority src="/brand-mark.png" width={34} />
          </div>
          <div>
            <strong>Coval HeYi</strong>
            <span>家庭健康记忆</span>
          </div>
        </div>

        <nav className="rail-nav">
          {navItems.map((item) => (
            <a className={item.active ? "active" : ""} href={item.href} key={item.label}>
              <item.icon size={17} />
              <span>{item.label}</span>
            </a>
          ))}
        </nav>

        <section className="memory-mini" aria-label="Coval AI memo lineage">
          <strong>家庭记忆链路</strong>
          <span>Coval 的记忆流：碎片上下文，到长期档案，再到复诊前 briefing。</span>
        </section>

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

        <p className="privacy-note" id="privacy-boundary">
          <ShieldCheck size={16} />
          公开演示只使用 synthetic/public-safe 样例；真实家庭资料留在本地。
        </p>
      </aside>

      <section className="workspace">
        <header className="patient-strip">
          <div>
            <span className="eyebrow">Coval Health Memo</span>
            <h1>{member.name} · {member.age} 岁</h1>
          </div>
          <div className="strip-meta">
            <span>{member.badges[0]}</span>
            <span>来源：{selected.inputType}</span>
            <span>类型：{selected.reportType}</span>
          </div>
          <div className="strip-status">
            <SlidersHorizontal size={16} />
            本地演示视图
          </div>
        </header>

        <header className="mobile-header">
          <select className="mobile-member-select" onChange={(event) => chooseMember(event.target.value)} value={member.id}>
            {familyMembers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <strong>新建记录</strong>
          <button disabled={!isOrganized || saved} type="button" onClick={saveToTimeline}>
            {saved ? "已保存" : "保存"}
          </button>
        </header>

        <div className="sheet-grid">
          <section className="record-panel" aria-label="新建记录" id="new-record">
            <div className="panel-title">
              <div>
                <h2>新建记录</h2>
                <p>只整理信息，不替代诊断或用药建议。</p>
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
            <p className="mode-hint">{modeHints[inputMode]}</p>

            <div className="record-facts" aria-label="记录来源和待补信息">
              {intakeFacts.map((fact) => (
                <span key={fact.label}>
                  <small>{fact.label}</small>
                  <strong>{fact.value}</strong>
                </span>
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

            <div className="record-needline" aria-label="保存前核对">
              <span>保存前核对</span>
              <strong>{selected.missingFields[0] ?? "暂无待补字段"}</strong>
            </div>

            <div className="record-actions">
              <button className="secondary-button" disabled title="公开 demo 不读取真实文件" type="button">
                <FileScan size={16} />
                本地 OCR 待接入
              </button>
              <button className="primary-button" onClick={organizeRecord} type="button">
                <ClipboardCheck size={16} />
                {isOrganized ? "重新整理" : "智能整理"}
              </button>
            </div>
          </section>

          <section className="review-panel" aria-label="结构化复核">
            <div className="panel-title">
              <div>
                <h2>家庭记忆复核</h2>
                <p>先把碎片整理成可核对事实，再进入本地家庭健康记忆。</p>
              </div>
              <button className="secondary-button" disabled={!isOrganized || saved} onClick={saveToTimeline} type="button">
                <Save size={16} />
                {saved ? "已保存" : "确认保存到健康记忆"}
              </button>
            </div>

            <section className="doctor-brief" aria-label="给医生看的摘要">
              <span>给医生看的摘要</span>
              <p>{isOrganized ? selected.summary : "点击智能整理后，这里会生成可带去复诊的摘要。"}</p>
            </section>

            <div className="memo-flow" aria-label="AI memo workflow">
              {memorySteps.map((step, index) => (
                <div className="memo-step" key={step.title}>
                  <span className="memo-index">{index + 1}</span>
                  <strong>{step.title}</strong>
                  <p>{step.detail}</p>
                </div>
              ))}
            </div>

            {isOrganized ? (
              <div className="review-table">
                <div className="review-head" role="row">
                  <span>项目</span>
                  <span>原文片段</span>
                  <span>结构化字段</span>
                  <span>状态</span>
                  <span>核对</span>
                </div>
                {reviewRows.map((row) => {
                  const checkedKey = `${selected.id}:${row.section}`;
                  const isChecked = Boolean(checkedRows[checkedKey]);
                  return (
                    <div className="review-row" role="row" key={row.section}>
                      <strong>{row.section}</strong>
                      <span>{row.source}</span>
                      <span>{row.field}</span>
                      <span className="row-status">{isChecked ? "家人已核对" : row.status}</span>
                      <button className={isChecked ? "verified" : ""} onClick={() => toggleReviewCheck(row.section)} type="button">
                        {isChecked ? "已核对" : row.status === "待补充" ? "补充" : "核对"}
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="review-empty">
                <ClipboardCheck size={18} />
                <strong>等待智能整理</strong>
                <p>先确认左侧原文，再生成可核对字段、复诊摘要和待补信息。</p>
              </div>
            )}
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

            <section className="inspector-block visit-prep-block">
              <div className="block-title">
                <span>复诊准备清单</span>
                <FileText size={17} />
              </div>
              <ul>
                {visitPrepItems.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>

            <section className="inspector-block">
              <div className="block-title">
                <span>待补信息</span>
                <Activity size={17} />
              </div>
              <div className="missing-checklist">
                <strong>{selected.missingFields.length > 0 ? `待补 ${selected.missingFields.length} 项` : "信息完整"}</strong>
                <ul>
                  {selected.missingFields.slice(0, 3).map((field) => (
                    <li key={field}>{field}</li>
                  ))}
                </ul>
                <span>{checkedCount}/{reviewRows.length} 项已核对</span>
              </div>
            </section>

            <section className="inspector-block automation-block" id="weekly-report">
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

            <section className="inspector-block scope-block">
              <div className="block-title">
                <span>项目边界</span>
                <LockKeyhole size={17} />
              </div>
              <ul>
                {scopeFacts.slice(0, 3).map((fact) => (
                  <li key={fact}>{fact}</li>
                ))}
              </ul>
            </section>

            <section className="inspector-block evidence-block" id="project-evidence">
              <div className="block-title">
                <span>模型证据</span>
                <TableProperties size={17} />
              </div>
              <table>
                <thead>
                  <tr>
                    <th>指标</th>
                    <th>来源</th>
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
            <span>{saved ? "已保存到健康记忆" : "长期健康记忆"}</span>
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
