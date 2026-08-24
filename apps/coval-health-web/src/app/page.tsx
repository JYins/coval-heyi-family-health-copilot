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
  RotateCcw,
  Save,
  ShieldCheck,
  SlidersHorizontal,
  TableProperties
} from "lucide-react";
import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import {
  evalEvidence,
  familyMembers,
  memorySteps,
  modeHints,
  samples,
  scopeFacts,
  type EvalEvidenceItem,
  type FamilyMember,
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
  { label: "手动记录", icon: FileText },
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

const apiBase = process.env.NEXT_PUBLIC_COVAL_API_BASE_URL ?? "http://127.0.0.1:8000";

type CanonicalRecord = {
  report_type: string;
  event_date: string | null;
  summary: string;
  symptoms: Array<{ text: string; onset_text?: string; negated?: boolean; source_locator?: object }>;
  medications: Array<{ name: string; event_type?: string; dose_text?: string; source_locator?: object }>;
  allergies: string[];
  observations: Array<{ name: string; value: string; unit?: string; source_locator?: object }>;
  appointments: Array<{ text: string; scheduled_at?: string | null; source_locator?: object }>;
  missing_fields: string[];
  safety: {
    state: SafetyState;
    category: string;
    message: string;
    unsafe_request_detected: boolean;
    forbidden_advice_generated: 0;
  };
};

type ApiRecord = {
  id: string;
  member_id: string;
  status: "candidate" | "approved" | "archived";
  candidate_id: string;
  candidate_revision: number;
  candidate: CanonicalRecord;
  canonical: CanonicalRecord | null;
  current_version_id: string | null;
  version_number: number | null;
  duplicate?: boolean;
  extraction: { provider: string; extraction_version: string };
};

type ServiceState = {
  state: "connecting" | "online" | "offline";
  databaseVersion?: number;
  provider?: string;
  gateMode?: string;
  realDataReady?: boolean;
};

type Capture = {
  source_artifact_id: string;
  member_id: string;
  state: "captured" | "processing" | "failed_retryable" | "needs_review" | "rejected" | "completed";
  attempt_count: number;
  last_error_code: string | null;
  record_id: string | null;
  retryable: boolean;
  source: { label: string; original_text: string; event_date: string | null };
};

type CaptureEnvelope = { capture: Capture; error?: { code: string; message: string } };

async function apiJson<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T & { code?: string; detail?: string };
  if (!response.ok) {
    throw new Error(`${data.code ?? `http_${response.status}`}: ${data.detail ?? "请求失败"}`);
  }
  return data;
}

function stableKey(prefix: string, value: unknown) {
  const text = JSON.stringify(value);
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(16)}`;
}

function inputModeValue(label: string): "text" | "ocr" | "voice" | "blood_pressure" {
  if (label === "OCR 文本") return "ocr";
  if (label === "语音转写") return "voice";
  if (label === "记录血压") return "blood_pressure";
  return "text";
}

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

function getReviewRows(sample: HealthSample, candidate: CanonicalRecord | null, sourceText = sample.note) {
  const symptoms = candidate ? candidate.symptoms.map((item) => item.text) : sample.structured.symptoms;
  const medications = candidate ? candidate.medications.map((item) => item.name) : sample.structured.medications;
  const observations = candidate
    ? candidate.observations.map((item) => `${item.name} ${item.value}${item.unit ?? ""}`)
    : [];
  const missingFields = candidate?.missing_fields ?? sample.missingFields;
  return [
    {
      key: "report_type" as const,
      section: "主诉",
      source: firstSentence(sourceText),
      field: candidate?.report_type ?? sample.reportType,
      status: "已归类",
      editable: true
    },
    {
      key: "symptoms" as const,
      section: "症状",
      source: listText(symptoms),
      field: listText(symptoms, ""),
      status: symptoms.length > 0 ? "已识别" : "空",
      editable: true
    },
    {
      key: "medications" as const,
      section: "用药",
      source: listText(medications),
      field: listText(medications, ""),
      status: medications.length > 0 ? "需核对" : "空",
      editable: true
    },
    {
      key: "observations" as const,
      section: "检查",
      source: observations.length > 0 ? listText(observations) : labText(sample),
      field: observations.length > 0 ? listText(observations) : labText(sample),
      status: observations.length > 0 || sample.structured.labs.length > 0 ? "已识别" : "空",
      editable: false
    },
    {
      key: "missing_fields" as const,
      section: "复诊问题",
      source: listText(missingFields),
      field: listText(missingFields, ""),
      status: missingFields.length > 0 ? "待补充" : "完整",
      editable: true
    }
  ];
}

function splitFields(value: string) {
  return value.split(/[、,，]/).map((item) => item.trim()).filter(Boolean);
}

export default function Home() {
  const [members, setMembers] = useState<FamilyMember[]>(familyMembers);
  const [memberId, setMemberId] = useState("mom");
  const [sampleId, setSampleId] = useState("symptom-note");
  const [inputMode, setInputMode] = useState("手动记录");
  const [noteText, setNoteText] = useState(samples[0].note);
  const [sourceLabel, setSourceLabel] = useState(samples[0].source);
  const [eventDate, setEventDate] = useState(samples[0].date);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [captures, setCaptures] = useState<Capture[]>([]);
  const [saved, setSaved] = useState(false);
  const [organizedSampleId, setOrganizedSampleId] = useState<string | null>(null);
  const [checkedRows, setCheckedRows] = useState<Record<string, boolean>>({});
  const [modelEvidence, setModelEvidence] = useState<EvalEvidenceItem[]>(evalEvidence);
  const [service, setService] = useState<ServiceState>({ state: "connecting" });
  const [apiError, setApiError] = useState<string | null>(null);
  const [actionState, setActionState] = useState<"idle" | "organizing" | "saving" | "undoing">("idle");
  const [record, setRecord] = useState<ApiRecord | null>(null);
  const [draftCandidate, setDraftCandidate] = useState<CanonicalRecord | null>(null);
  const [newMemberName, setNewMemberName] = useState("");
  const [newMemberAge, setNewMemberAge] = useState("40");
  const [creatingMember, setCreatingMember] = useState(false);
  const [syntheticOnlyConfirmed, setSyntheticOnlyConfirmed] = useState(false);

  const member = members.find((item) => item.id === memberId) ?? members[0] ?? familyMembers[0];
  const memberSamples = samples.filter((sample) => sample.memberId === member.id);
  const selected =
    samples.find((sample) => sample.id === sampleId && sample.memberId === member.id) ??
    memberSamples[0] ??
    samples[0];

  const visibleTimeline = useMemo(
    () => timeline.filter((item) => item.memberId === member.id).sort((a, b) => b.date.localeCompare(a.date)),
    [member.id, timeline]
  );

  const currentDraftKey = stableKey("draft", {
    memberId: member.id, noteText, inputMode, sourceLabel, eventDate
  });
  const reviewRows = getReviewRows(selected, draftCandidate, noteText);
  const isOrganized = organizedSampleId === currentDraftKey && Boolean(draftCandidate && record);
  const activeSafety = draftCandidate?.safety.state ?? selected.safety;
  const activeMissingFields = draftCandidate?.missing_fields ?? selected.missingFields;
  const intakeFacts = [
    { label: "来源", value: sourceLabel },
    { label: "日期", value: eventDate },
    { label: "待补", value: activeMissingFields.length > 0 ? `${activeMissingFields.length} 项` : "完整" }
  ];
  const visitPrepItems = [
    (draftCandidate?.medications.length ?? selected.structured.medications.length) > 0
      ? `核对用药：${(draftCandidate?.medications.map((item) => item.name) ?? selected.structured.medications).slice(0, 2).join("、")}`
      : "带上近期用药清单",
    (draftCandidate?.allergies.length ?? selected.structured.allergies.length) > 0
      ? `过敏史：${(draftCandidate?.allergies ?? selected.structured.allergies).slice(0, 2).join("、")}`
      : "确认过敏史",
    activeMissingFields[0] ? `补充：${activeMissingFields[0]}` : "摘要可用于复诊沟通"
  ];
  const checkedCount = reviewRows.filter((row) => checkedRows[`${selected.id}:${row.section}`]).length;
  const evidenceRows = evidenceOrder
    .map((label) => modelEvidence.find((item) => item.label === label))
    .filter((item): item is EvalEvidenceItem => Boolean(item))
    .filter((item, index, items) => items.findIndex((candidate) => candidate.label === item.label) === index)
    .slice(0, 6);
  const gateContractValid = service.gateMode === "synthetic_public_only" && service.realDataReady === false;
  const canWrite = service.state === "online" && gateContractValid && syntheticOnlyConfirmed;

  useEffect(() => {
    const controller = new AbortController();
    async function loadService() {
      setService({ state: "connecting" });
      try {
        const [healthResponse, evidenceResponse, timelineResponse, membersResponse, capturesResponse] = await Promise.all([
          fetch(`${apiBase}/health`, { signal: controller.signal }),
          fetch(`${apiBase}/model-evidence`, { signal: controller.signal }),
          fetch(`${apiBase}/timeline?member_id=${encodeURIComponent(member.id)}`, { signal: controller.signal }),
          fetch(`${apiBase}/family-members`, { signal: controller.signal }),
          fetch(`${apiBase}/ingestions?member_id=${encodeURIComponent(member.id)}`, { signal: controller.signal })
        ]);
        const health = await apiJson<{
          llm_service: string;
          database: { status: string; schema_version: number };
          real_data_gate: { mode: string; ready: boolean };
        }>(healthResponse);
        const data = await apiJson<{
          base_model: string;
          adapter: string;
          status: string;
          metrics: EvalEvidenceItem[];
        }>(evidenceResponse);
        const timelineData = await apiJson<Array<{
          id: string;
          member_id: string;
          date: string;
          title: string;
          detail: string;
          tag: string;
          safety: SafetyState;
          current_version_id: string;
          version_number: number;
        }>>(timelineResponse);
        const memberData = await apiJson<FamilyMember[]>(membersResponse);
        const captureData = await apiJson<Capture[]>(capturesResponse);
        setService({
          state: "online",
          databaseVersion: health.database.schema_version,
          provider: health.llm_service,
          gateMode: health.real_data_gate.mode,
          realDataReady: health.real_data_gate.ready
        });
        setApiError(null);
        setMembers(memberData);
        setCaptures(captureData);
        setTimeline(timelineData.map((item) => ({
          id: item.id,
          memberId: item.member_id,
          date: item.date,
          title: item.title,
          detail: item.detail,
          tag: item.tag,
          safety: item.safety,
          currentVersionId: item.current_version_id,
          versionNumber: item.version_number
        })));
        setModelEvidence([
          { label: "Base model", value: data.base_model, source: "model" },
          { label: "Default candidate", value: data.adapter, source: data.status },
          { label: "Training data", value: "26 synthetic rows", source: "sft_v2 manifest" },
          ...data.metrics,
          { label: "RAG phase", value: "retrieval scaffold only", source: "rag_v0" }
        ]);
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setService({ state: "offline" });
        setTimeline([]);
        setApiError(`本地 API 不可用，写入已禁用。${error instanceof Error ? ` ${error.message}` : ""}`);
      }
    }

    void loadService();
    return () => controller.abort();
  }, [member.id]);

  function chooseMember(nextMemberId: string) {
    const nextSample = samples.find((sample) => sample.memberId === nextMemberId);
    setMemberId(nextMemberId);
    if (nextSample) {
      setSampleId(nextSample.id);
      setInputMode(nextSample.inputType === "安全请求" ? "手动记录" : nextSample.inputType);
      setNoteText(nextSample.note);
      setSourceLabel(nextSample.source);
      setEventDate(nextSample.date);
    }
    setOrganizedSampleId(null);
    setRecord(null);
    setDraftCandidate(null);
    setSaved(false);
  }

  function chooseSample(sample: HealthSample) {
    setSampleId(sample.id);
    setInputMode(sample.inputType === "安全请求" ? "手动记录" : sample.inputType);
    setNoteText(sample.note);
    setSourceLabel(sample.source);
    setEventDate(sample.date);
    setOrganizedSampleId(null);
    setRecord(null);
    setDraftCandidate(null);
    setSaved(false);
  }

  async function refreshTimeline() {
    const response = await fetch(`${apiBase}/timeline?member_id=${encodeURIComponent(member.id)}`);
    const items = await apiJson<Array<{
      id: string; member_id: string; date: string; title: string; detail: string;
      tag: string; safety: SafetyState; current_version_id: string; version_number: number;
    }>>(response);
    setTimeline(items.map((item) => ({
      id: item.id, memberId: item.member_id, date: item.date, title: item.title,
      detail: item.detail, tag: item.tag, safety: item.safety,
      currentVersionId: item.current_version_id, versionNumber: item.version_number
    })));
  }

  async function refreshCaptures() {
    const response = await fetch(`${apiBase}/ingestions?member_id=${encodeURIComponent(member.id)}`);
    setCaptures(await apiJson<Capture[]>(response));
  }

  function resetOrganizedDraft() {
    setOrganizedSampleId(null);
    setRecord(null);
    setDraftCandidate(null);
    setSaved(false);
  }

  async function organizeRecord() {
    if (!canWrite) return;
    setActionState("organizing");
    setApiError(null);
    const body = {
      member_id: member.id,
      text: noteText,
      input_mode: inputModeValue(inputMode),
      event_date: eventDate || null,
      source_label: sourceLabel,
      idempotency_key: stableKey("capture", {
        memberId: member.id, noteText, inputMode, eventDate, sourceLabel
      })
    };
    try {
      const result = await apiJson<ApiRecord | CaptureEnvelope>(await fetch(`${apiBase}/ingestions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      }));
      if ("capture" in result) {
        setApiError(result.error?.message ?? "原文已保存，正在等待本地模型完成整理。");
        await refreshCaptures();
        return;
      }
      setRecord(result);
      setDraftCandidate(result.canonical ?? result.candidate);
      setOrganizedSampleId(currentDraftKey);
      setSaved(result.status === "approved");
      await refreshTimeline();
      await refreshCaptures();
    } catch (error) {
      setApiError(`整理失败；若原文已经持久化，可在“待处理原文”中恢复。${error instanceof Error ? ` ${error.message}` : ""}`);
    } finally {
      setActionState("idle");
    }
  }

  async function retryCapture(capture: Capture) {
    if (!canWrite) return;
    setActionState("organizing");
    setApiError(null);
    try {
      const result = await apiJson<ApiRecord | CaptureEnvelope>(await fetch(
        `${apiBase}/ingestions/${capture.source_artifact_id}/retry`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ member_id: member.id })
        }
      ));
      if ("capture" in result) {
        setApiError(result.error?.message ?? "原文仍在处理中。");
      } else {
        setRecord(result);
        setDraftCandidate(result.canonical ?? result.candidate);
        setNoteText(capture.source.original_text);
        setSourceLabel(capture.source.label);
        setEventDate(capture.source.event_date ?? "");
        setOrganizedSampleId(stableKey("draft", {
          memberId: member.id,
          noteText: capture.source.original_text,
          inputMode,
          sourceLabel: capture.source.label,
          eventDate: capture.source.event_date ?? ""
        }));
      }
      await refreshCaptures();
    } catch (error) {
      setApiError(`重试失败。${error instanceof Error ? ` ${error.message}` : ""}`);
    } finally {
      setActionState("idle");
    }
  }

  async function rejectCapture(capture: Capture) {
    if (!canWrite) return;
    await apiJson(await fetch(`${apiBase}/ingestions/${capture.source_artifact_id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ member_id: member.id })
    }));
    await refreshCaptures();
  }

  async function resumeCapture(capture: Capture) {
    if (!capture.record_id) return;
    const nextRecord = await apiJson<ApiRecord>(await fetch(
      `${apiBase}/records/${capture.record_id}?member_id=${encodeURIComponent(member.id)}`
    ));
    setNoteText(capture.source.original_text);
    setSourceLabel(capture.source.label);
    setEventDate(capture.source.event_date ?? "");
    setInputMode("手动记录");
    setRecord(nextRecord);
    setDraftCandidate(nextRecord.canonical ?? nextRecord.candidate);
    setOrganizedSampleId(stableKey("draft", {
      memberId: member.id,
      noteText: capture.source.original_text,
      inputMode: "手动记录",
      sourceLabel: capture.source.label,
      eventDate: capture.source.event_date ?? ""
    }));
  }

  async function createMember() {
    const age = Number(newMemberAge);
    if (!newMemberName.trim() || !Number.isInteger(age) || !canWrite) return;
    setCreatingMember(true);
    try {
      const created = await apiJson<FamilyMember>(await fetch(`${apiBase}/family-members`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newMemberName.trim(), relation: "家庭成员", age, profile: "", badges: ["本地档案"]
        })
      }));
      setMembers((items) => [...items, created]);
      setNewMemberName("");
      chooseMember(created.id);
      setNoteText("");
      setSourceLabel("家庭手动记录");
      setEventDate(new Date().toISOString().slice(0, 10));
      setInputMode("手动记录");
    } catch (error) {
      setApiError(`新增成员失败。${error instanceof Error ? ` ${error.message}` : ""}`);
    } finally {
      setCreatingMember(false);
    }
  }

  function toggleReviewCheck(section: string) {
    const key = `${selected.id}:${section}`;
    setCheckedRows((items) => ({ ...items, [key]: !items[key] }));
  }

  function updateReviewField(key: string, value: string) {
    setDraftCandidate((current) => {
      if (!current) return current;
      if (key === "report_type") return { ...current, report_type: value };
      if (key === "symptoms") {
        return { ...current, symptoms: splitFields(value).map((text) => ({ text, source_locator: {} })) };
      }
      if (key === "medications") {
        return { ...current, medications: splitFields(value).map((name) => ({ name, event_type: "reported", source_locator: {} })) };
      }
      if (key === "missing_fields") return { ...current, missing_fields: splitFields(value) };
      return current;
    });
    setSaved(false);
  }

  async function saveToTimeline() {
    if (!isOrganized || !record || !draftCandidate || !canWrite) return;
    setActionState("saving");
    setApiError(null);
    try {
      let nextRecord: ApiRecord;
      if (record.status === "candidate") {
        const editBody = {
          member_id: member.id,
          base_candidate_id: record.candidate_id,
          base_candidate_revision: record.candidate_revision,
          candidate: draftCandidate,
          idempotency_key: stableKey(
            `candidate-${record.id}-${record.candidate_id}-r${record.candidate_revision}`,
            draftCandidate
          )
        };
        const edited = await apiJson<ApiRecord>(await fetch(`${apiBase}/records/${record.id}/candidate`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(editBody)
        }));
        nextRecord = await apiJson<ApiRecord>(await fetch(`${apiBase}/records/${record.id}/approve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            member_id: member.id,
            candidate_id: edited.candidate_id,
            candidate_revision: edited.candidate_revision,
            idempotency_key: `approve-${record.id}-${edited.candidate_id}`
          })
        }));
      } else {
        nextRecord = await apiJson<ApiRecord>(await fetch(`${apiBase}/records/${record.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            member_id: member.id,
            base_version_id: record.current_version_id,
            record: draftCandidate,
            idempotency_key: stableKey(`record-${record.id}-${record.current_version_id}`, draftCandidate)
          })
        }));
      }
      setRecord(nextRecord);
      setDraftCandidate(nextRecord.canonical ?? nextRecord.candidate);
      setSaved(true);
      await refreshTimeline();
    } catch (error) {
      setApiError(`保存失败；页面不会显示假成功。${error instanceof Error ? ` ${error.message}` : ""}`);
    } finally {
      setActionState("idle");
    }
  }

  async function undoLastEdit() {
    if (!record?.current_version_id || (record.version_number ?? 0) <= 1 || !canWrite) return;
    setActionState("undoing");
    setApiError(null);
    try {
      const versions = await apiJson<Array<{ id: string; version_number: number }>>(
        await fetch(`${apiBase}/records/${record.id}/versions?member_id=${encodeURIComponent(member.id)}`)
      );
      const target = versions.find((item) => item.version_number === (record.version_number ?? 1) - 1);
      if (!target) throw new Error("找不到上一版本");
      const nextRecord = await apiJson<ApiRecord>(await fetch(`${apiBase}/records/${record.id}/undo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          member_id: member.id,
          base_version_id: record.current_version_id,
          target_version_id: target.id,
          idempotency_key: `undo-${record.id}-${record.current_version_id}-${target.id}`
        })
      }));
      setRecord(nextRecord);
      setDraftCandidate(nextRecord.canonical);
      setSaved(true);
      await refreshTimeline();
    } catch (error) {
      setApiError(`撤销失败，历史版本未被覆盖。${error instanceof Error ? ` ${error.message}` : ""}`);
    } finally {
      setActionState("idle");
    }
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
          {members.map((item) => (
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
          <div className="member-create">
            <input
              aria-label="虚构成员名称"
              onChange={(event) => setNewMemberName(event.target.value)}
              placeholder="虚构成员名称"
              value={newMemberName}
            />
            <input
              aria-label="新成员年龄"
              inputMode="numeric"
              min="0"
              max="130"
              onChange={(event) => setNewMemberAge(event.target.value)}
              type="number"
              value={newMemberAge}
            />
            <button disabled={creatingMember || !canWrite} onClick={createMember} type="button">
              {creatingMember ? "添加中" : "添加"}
            </button>
          </div>
        </section>

        <p className="privacy-note" id="privacy-boundary">
          <ShieldCheck size={16} />
          本公开版本仅允许 synthetic/public-safe 样例；禁止输入真实家庭或患者资料。
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
            {service.state === "online"
              ? `API 已连接 · SQLite v${service.databaseVersion} · 推理 ${service.provider}`
              : service.state === "connecting"
                ? "正在连接本地 API"
                : "API 离线 · 写入已禁用"}
          </div>
        </header>

        <header className="mobile-header">
          <select className="mobile-member-select" onChange={(event) => chooseMember(event.target.value)} value={member.id}>
            {members.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
          <strong>新建记录</strong>
          <button disabled={!isOrganized || saved || actionState !== "idle" || !canWrite} type="button" onClick={saveToTimeline}>
            {actionState === "saving" ? "保存中" : saved ? "已保存" : "保存"}
          </button>
        </header>

        <div className="sheet-grid">
          <section className="record-panel" aria-label="新建记录" id="new-record">
            <div className="panel-title">
              <div>
                <h2>新建记录</h2>
                <p>只整理信息，不替代诊断或用药建议。</p>
              </div>
              <span className={`state-label ${safetyTone[activeSafety]}`}>{safetyLabel[activeSafety]}</span>
            </div>

            <label className="synthetic-gate">
              <input
                aria-label="仅使用虚构或公开数据"
                checked={syntheticOnlyConfirmed}
                disabled={!gateContractValid || service.state !== "online"}
                onChange={(event) => setSyntheticOnlyConfirmed(event.target.checked)}
                type="checkbox"
              />
              <span>
                <strong>仅限虚构或公开数据</strong>
                本版本禁止输入真实姓名、报告、症状、用药或家庭资料；数据库与备份未加密，且没有鉴权。
              </span>
            </label>

            <div className="mode-control" role="tablist" aria-label="输入方式">
              {inputModes.map((mode) => (
                <button
                  className={inputMode === mode.label ? "active" : ""}
                  key={mode.label}
                  onClick={() => {
                    setInputMode(mode.label);
                    resetOrganizedDraft();
                  }}
                  type="button"
                >
                  <mode.icon size={16} />
                  {mode.label}
                </button>
              ))}
            </div>
            <p className="mode-hint">{modeHints[inputMode]}</p>
            {apiError ? <p className="api-error" role="alert">{apiError}</p> : null}

            <div className="record-facts" aria-label="记录来源和待补信息">
              {intakeFacts.map((fact) => (
                <span key={fact.label}>
                  <small>{fact.label}</small>
                  <strong>{fact.value}</strong>
                </span>
              ))}
            </div>

            <div className="record-meta-inputs">
              <label>
                <span>来源</span>
                <input
                  aria-label="记录来源"
                  maxLength={160}
                  onChange={(event) => {
                    setSourceLabel(event.target.value);
                    resetOrganizedDraft();
                  }}
                  value={sourceLabel}
                />
              </label>
              <label>
                <span>事件日期</span>
                <input
                  aria-label="事件日期"
                  onChange={(event) => {
                    setEventDate(event.target.value);
                    resetOrganizedDraft();
                  }}
                  type="date"
                  value={eventDate}
                />
              </label>
            </div>

            <textarea
              aria-label="健康记录内容"
              maxLength={8000}
              onChange={(event) => {
                setNoteText(event.target.value);
                resetOrganizedDraft();
              }}
              value={noteText}
            />

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

            {captures.some((item) => ["captured", "processing", "failed_retryable", "needs_review"].includes(item.state)) ? (
              <section className="capture-inbox" aria-label="待处理原文">
                <strong>待处理原文</strong>
                {captures
                  .filter((item) => ["captured", "processing", "failed_retryable", "needs_review"].includes(item.state))
                  .slice(0, 3)
                  .map((item) => (
                    <article key={item.source_artifact_id}>
                      <span>{item.source.label} · {item.state}</span>
                      <small>{firstSentence(item.source.original_text)}</small>
                      <div>
                        {item.state === "needs_review" ? (
                          <button onClick={() => void resumeCapture(item)} type="button">继续审核</button>
                        ) : item.retryable ? (
                          <button disabled={actionState !== "idle" || !canWrite} onClick={() => void retryCapture(item)} type="button">重试</button>
                        ) : null}
                        {item.state !== "processing" || item.retryable ? (
                          <button disabled={!canWrite} onClick={() => void rejectCapture(item)} type="button">拒绝</button>
                        ) : null}
                      </div>
                    </article>
                  ))}
              </section>
            ) : null}

            <div className="record-needline" aria-label="保存前核对">
              <span>保存前核对</span>
              <strong>{selected.missingFields[0] ?? "暂无待补字段"}</strong>
            </div>

            <div className="record-actions">
              <button className="secondary-button" disabled title="公开 demo 不读取真实文件" type="button">
                <FileScan size={16} />
                本地 OCR 待接入
              </button>
              <button
                className="primary-button"
                disabled={!canWrite || actionState !== "idle" || !noteText.trim() || !sourceLabel.trim()}
                onClick={organizeRecord}
                type="button"
              >
                <ClipboardCheck size={16} />
                {actionState === "organizing" ? "整理中" : isOrganized ? "重新整理" : "智能整理"}
              </button>
            </div>
          </section>

          <section className="review-panel" aria-label="结构化复核">
            <div className="panel-title">
              <div>
                <h2>家庭记忆复核</h2>
                <p>先把虚构/公开样例整理成可核对事实，再进入本地演示记忆。</p>
              </div>
              <div className="review-actions">
                <button
                  className="secondary-button"
                  disabled={!record?.current_version_id || (record.version_number ?? 0) <= 1 || actionState !== "idle" || !canWrite}
                  onClick={undoLastEdit}
                  type="button"
                >
                  <RotateCcw size={16} />
                  {actionState === "undoing" ? "撤销中" : "撤销到上一版"}
                </button>
                <button
                  className="secondary-button"
                  disabled={!isOrganized || saved || actionState !== "idle" || !canWrite}
                  onClick={saveToTimeline}
                  type="button"
                >
                  <Save size={16} />
                  {actionState === "saving" ? "服务器保存中" : saved ? `已保存 v${record?.version_number ?? 1}` : "确认保存到健康记忆"}
                </button>
              </div>
            </div>

            <section className="doctor-brief" aria-label="给医生看的摘要">
              <span>给医生看的摘要</span>
              {isOrganized && draftCandidate ? (
                <textarea
                  aria-label="医生摘要"
                  onChange={(event) => {
                    setDraftCandidate({ ...draftCandidate, summary: event.target.value });
                    setSaved(false);
                  }}
                  value={draftCandidate.summary}
                />
              ) : (
                <p>点击智能整理后，这里会生成可带去复诊的摘要。</p>
              )}
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
                      {row.editable ? (
                        <input
                          aria-label={`${row.section} 结构化字段`}
                          onChange={(event) => updateReviewField(row.key, event.target.value)}
                          value={row.field}
                        />
                      ) : (
                        <span>{row.field}</span>
                      )}
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
              <strong className={safetyTone[activeSafety]}>{safetyLabel[activeSafety]}</strong>
              <p role={activeSafety === "escalated" ? "alert" : undefined}>
                {draftCandidate?.safety.message ?? safetyCopy[activeSafety]}
              </p>
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
                <strong>{activeMissingFields.length > 0 ? `待补 ${activeMissingFields.length} 项` : "信息完整"}</strong>
                <ul>
                  {activeMissingFields.slice(0, 3).map((field) => (
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
                  计划中 · 调度器未接入
                </span>
              </div>
              <div className="automation-row">
                <Bell size={17} />
                <span>
                  <strong>家庭周报</strong>
                  计划中 · worker 未接入
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
              <strong>{item.title}{item.versionNumber ? ` · v${item.versionNumber}` : ""}</strong>
              <span>{item.detail}</span>
            </article>
          ))}
          {visibleTimeline.length === 0 ? (
            <article>
              <time>尚无记录</time>
              <strong>{service.state === "online" ? "等待确认保存" : "API 离线"}</strong>
              <span>只有服务器确认后的记录才会出现在这里。</span>
            </article>
          ) : null}
        </section>
      </section>
    </main>
  );
}
