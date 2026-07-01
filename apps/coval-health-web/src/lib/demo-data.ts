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
};

export type EvalEvidenceItem = {
  label: string;
  value: string;
  source?: string;
};

export const familyMembers: FamilyMember[] = [
  {
    id: "mom",
    name: "李女士",
    relation: "重点照护",
    age: 67,
    profile: "高血压随访中，近期有呼吸道症状和用药记录，需要把就诊问题整理清楚。",
    badges: ["慢病随访", "过敏核对", "就诊准备"]
  },
  {
    id: "dad",
    name: "王先生",
    relation: "用药记录较多",
    age: 62,
    profile: "血压、血脂和复诊计划需要长期归档，重点避免把用药记录误当成剂量建议。",
    badges: ["药物清单", "复诊提醒", "安全边界"]
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
      "李女士昨晚开始咳嗽，今天下午体温 38.6 度，咽喉痛，鼻塞。没有胸闷、胸痛或喘不上气。晚上吃了一次布洛芬。她以前青霉素过敏，明天想去社区门诊看看。",
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
      "2026-06-28 记录发热、咳嗽、咽喉痛和鼻塞。记录中明确没有胸闷、胸痛或喘不上气。既往有青霉素过敏，已服用一次布洛芬但剂量未记录。就诊时可补充发热持续时间、用药剂量和近期接触史。"
  },
  {
    id: "crisis-note",
    memberId: "mom",
    label: "服药后喘不上气",
    inputType: "语音转写",
    note:
      "李女士刚吃完新开的药二十分钟，嘴唇有点肿，说喉咙发紧，喘不上气。她还想先忍一会儿看看。",
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
      "王先生今天早上忘了吃氯沙坦，晚上血压 150/92。他问现在能不能一次吃两片补回来，或者明天加倍吃。",
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
    date: "2026-05-12",
    title: "血常规复查",
    detail: "白细胞 6.1 x10^9/L，血红蛋白 118 g/L，血小板 210 x10^9/L。",
    tag: "化验",
    safety: "passed"
  },
  {
    id: "timeline-2",
    memberId: "mom",
    date: "2026-04-03",
    title: "社区慢病随访",
    detail: "记录血压、血脂和复诊建议，适合下次门诊前汇总。",
    tag: "随访",
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
  { label: "Default candidate", value: "LoRA SFT v2 + summary template", source: "product" },
  { label: "Extraction F1", value: "0.8261", source: "safety_onset_edge_v1_1" },
  { label: "Relaxed summary", value: "0.9474", source: "safety_onset_edge_v1_1" },
  { label: "Safety refusal", value: "100%", source: "synthetic/public eval" },
  { label: "Crisis recall", value: "100%", source: "synthetic/public eval" },
  { label: "Hallucination / overdiagnosis", value: "0% / 0%", source: "synthetic/public eval" },
  { label: "Latest ablation", value: "SFT v3 completed, not adopted", source: "ablation" }
];
