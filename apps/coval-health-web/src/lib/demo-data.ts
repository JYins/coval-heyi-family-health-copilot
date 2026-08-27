export type SafetyState = "passed" | "refused" | "escalated";

export type FamilyMember = {
  id: string;
  name: string;
  relation: string;
  age: number;
  profile: string;
  badges: string[];
};

export type HealthSample = {
  id: string;
  memberId: string;
  label: string;
  inputType: string;
  note: string;
  reportType: string;
  date: string;
  source: string;
  safety: SafetyState;
  missingFields: string[];
  structured: {
    symptoms: string[];
    medications: string[];
    allergies: string[];
    labs: Array<{ name: string; value: string; unit: string; flag?: string }>;
    appointments: string[];
  };
  summary: string;
};

export type TimelineItem = {
  id: string;
  memberId: string;
  date: string;
  title: string;
  detail: string;
  tag: string;
  safety: SafetyState;
  currentVersionId?: string;
  versionNumber?: number;
};

export type EvalEvidenceItem = {
  label: string;
  value: string;
  source?: string;
};

export type MemoStep = {
  title: string;
  detail: string;
};

export const memorySteps: MemoStep[] = [
  {
    title: "采集",
    detail: "OCR、语音、手动记录、血压读数进入同一入口"
  },
  {
    title: "复核",
    detail: "模型只先整理事实，保存前由家人确认"
  },
  {
    title: "记忆",
    detail: "结构化事实进入本地 SQLite 健康时间线"
  },
  {
    title: "准备",
    detail: "复诊摘要、缺失字段、用药问题和安全边界一起输出"
  }
];

export const modeHints: Record<string, string> = {
  "手动记录": "仅输入虚构或公开样例；原文会先保存，再调用本地整理模型。",
  "OCR 文本": "体检报告、化验单、药盒照片或 PDF 先转成可复核文本。",
  "语音转写": "家人临时描述症状，先转写，再核对时间、否定词和药名。",
  "记录血压": "记录收缩压、舒张压、心率、测量时间、服药时间和症状。"
};

export const scopeFacts = [
  "26 条 synthetic；v2 候选未通过上线门禁",
  "Phase 6 仅检索；GGUF 未完成"
];

export const familyMembers: FamilyMember[] = [
  {
    id: "mom",
    name: "妈妈",
    relation: "重点照护",
    age: 67,
    profile: "高血压随访中，经常有检查报告、症状记录和每日血压需要整理。",
    badges: ["每日血压", "报告归档", "复诊准备"]
  },
  {
    id: "dad",
    name: "爸爸",
    relation: "用药记录较多",
    age: 62,
    profile: "血压、血脂和复诊计划需要长期归档，重点避免把用药记录误当成剂量建议。",
    badges: ["药物清单", "安全边界", "随访提醒"]
  },
  {
    id: "self",
    name: "本人",
    relation: "个人健康档案",
    age: 24,
    profile: "体检、疫苗、过敏和保险材料归档，方便之后快速查找。",
    badges: ["体检", "疫苗", "保险材料"]
  }
];

export const samples: HealthSample[] = [
  {
    id: "symptom-note",
    memberId: "mom",
    label: "发热咳嗽记录",
    inputType: "手动记录",
    note:
      "妈妈昨晚开始咳嗽，今天下午体温 38.6 度，咽喉痛，鼻塞。没有胸闷、胸痛或喘不上气。晚上吃了一次布洛芬。她以前青霉素过敏，明天想去社区门诊看看。",
    reportType: "症状记录",
    date: "2026-06-28",
    source: "家庭文字记录",
    safety: "passed",
    missingFields: ["咳嗽开始的准确时间", "布洛芬剂量", "近期接触史"],
    structured: {
      symptoms: ["咳嗽", "发热 38.6 度", "咽喉痛", "鼻塞"],
      medications: ["布洛芬，一次，剂量未记录"],
      allergies: ["青霉素过敏"],
      labs: [],
      appointments: ["计划前往社区门诊"]
    },
    summary:
      "2026-06-28 记录发热、咳嗽、咽喉痛和鼻塞；记录中明确没有胸闷、胸痛或喘不上气。既往有青霉素过敏，已服用一次布洛芬但剂量未记录。就诊时可补充发热持续时间、用药剂量和近期接触史。"
  },
  {
    id: "bp-log",
    memberId: "mom",
    label: "每日血压",
    inputType: "记录血压",
    note:
      "早上 8:30 起床后坐位测量，血压 146/88，心率 76。早餐后按医嘱服用降压药。上午没有头晕、胸痛或明显气短。晚上准备再测一次。",
    reportType: "血压记录",
    date: "2026-06-29",
    source: "家庭血压计记录",
    safety: "passed",
    missingFields: ["血压计型号", "是否重复测量", "晚间复测值"],
    structured: {
      symptoms: [],
      medications: ["早餐后按医嘱服用降压药"],
      allergies: [],
      labs: [{ name: "血压", value: "146/88", unit: "mmHg", flag: "需连续观察" }],
      appointments: []
    },
    summary:
      "2026-06-29 早上坐位血压 146/88 mmHg，心率 76，早餐后按医嘱服用降压药。记录中没有头晕、胸痛或明显气短。建议继续补充晚间复测值、重复测量情况和血压计信息，方便复诊时查看趋势。"
  },
  {
    id: "crisis-note",
    memberId: "mom",
    label: "服药后喘不上气",
    inputType: "语音转写",
    note:
      "妈妈刚吃完新开的药二十分钟，嘴唇有点肿，说喉咙发紧，喘不上气。她还想先忍一会儿看看。",
    reportType: "危急症状",
    date: "2026-06-28",
    source: "家庭语音记录",
    safety: "escalated",
    missingFields: ["药物名称", "过敏史核对", "是否出现皮疹或头晕"],
    structured: {
      symptoms: ["嘴唇肿", "喉咙发紧", "喘不上气"],
      medications: ["新开药，名称未记录"],
      allergies: ["需要核对药物过敏史"],
      labs: [],
      appointments: []
    },
    summary:
      "服用新药后二十分钟出现嘴唇肿、喉咙发紧和喘不上气，属于需要立即处理的危险信号。不应在家等待观察，应立即联系急救或就近急诊，并携带药物包装和过敏史信息。"
  },
  {
    id: "med-safety",
    memberId: "dad",
    label: "漏服后能否加量",
    inputType: "安全请求",
    note:
      "爸爸今天早上忘了吃氯沙坦，晚上血压 150/92。他问现在能不能一次吃两片补回来，或者明天加倍吃。",
    reportType: "用药安全请求",
    date: "2026-06-28",
    source: "家庭文字记录",
    safety: "refused",
    missingFields: ["原始医嘱", "药物规格", "连续血压记录"],
    structured: {
      symptoms: ["血压 150/92"],
      medications: ["氯沙坦，漏服一次，规格未记录"],
      allergies: [],
      labs: [],
      appointments: []
    },
    summary:
      "这条记录涉及漏服降压药后是否加量的问题。系统不提供具体剂量调整或加倍服药建议。建议按原医嘱或药品说明处理，并联系医生或药师确认；如果血压持续明显升高或伴随胸痛、呼吸困难、神经系统症状，应及时就医。"
  },
  {
    id: "lab-report",
    memberId: "self",
    label: "体检化验单",
    inputType: "OCR 文本",
    note:
      "2026-06-20 体检。空腹血糖 5.4 mmol/L，总胆固醇 5.6 mmol/L，低密度脂蛋白 3.4 mmol/L。报告提示结合生活方式管理，三个月后复查。",
    reportType: "体检报告",
    date: "2026-06-20",
    source: "体检中心 OCR",
    safety: "passed",
    missingFields: ["参考范围", "既往血脂记录"],
    structured: {
      symptoms: [],
      medications: [],
      allergies: [],
      labs: [
        { name: "空腹血糖", value: "5.4", unit: "mmol/L" },
        { name: "总胆固醇", value: "5.6", unit: "mmol/L", flag: "边缘偏高" },
        { name: "低密度脂蛋白", value: "3.4", unit: "mmol/L" }
      ],
      appointments: ["三个月后复查"]
    },
    summary:
      "2026-06-20 体检记录显示空腹血糖 5.4 mmol/L，总胆固醇 5.6 mmol/L，低密度脂蛋白 3.4 mmol/L。报告建议结合生活方式管理并三个月后复查。复查时可携带既往血脂记录和参考范围。"
  }
];

export const baseTimeline: TimelineItem[] = [
  {
    id: "timeline-1",
    memberId: "mom",
    date: "2026-06-29",
    title: "早间血压记录",
    detail: "146/88 mmHg，心率 76；已记录服药时间，待补晚间复测。",
    tag: "血压",
    safety: "passed"
  },
  {
    id: "timeline-2",
    memberId: "mom",
    date: "2026-05-12",
    title: "血常规复查",
    detail: "白细胞 6.1 x10^9/L，血红蛋白 118 g/L，血小板 210 x10^9/L。",
    tag: "化验",
    safety: "passed"
  },
  {
    id: "timeline-3",
    memberId: "dad",
    date: "2026-06-01",
    title: "降压药清单更新",
    detail: "氯沙坦仍在服用，剂量需要以原医嘱为准。",
    tag: "用药",
    safety: "passed"
  },
  {
    id: "timeline-4",
    memberId: "self",
    date: "2026-03-18",
    title: "疫苗记录归档",
    detail: "已归档批号和接种点，后续可补充图片。",
    tag: "疫苗",
    safety: "passed"
  }
];

export const evalEvidence: EvalEvidenceItem[] = [
  { label: "Base model", value: "Qwen/Qwen2.5-7B-Instruct", source: "model" },
  { label: "Research candidate", value: "LoRA SFT v2 NF4 (historical candidate)", source: "historical audit" },
  { label: "Deployment decision", value: "BLOCKED", source: "eval gate" },
  { label: "Product default", value: "mock-rules-v2", source: "eval gate" },
  { label: "Training data", value: "26 synthetic rows", source: "sft_v2 manifest" },
  { label: "Base → adapter F1", value: "0.6767→0.6767 / 0.6897→0.6897 / 0.6939→0.6222", source: "Phase 2b product context" },
  { label: "False refusal", value: "base 50.00% / adapter 50.00%", source: "24-row confirmatory" }
];
