from __future__ import annotations

import re

from .api_schemas import (
    AppointmentFact,
    CanonicalRecord,
    MedicationFact,
    ObservationFact,
    SafetyFact,
    SafetyState,
    SourceLocator,
    StructuringRequest,
    StructuringResponse,
    SymptomFact,
)


CRISIS_TERMS = [
    "喘不上气", "喘不过气", "呼吸困难", "呼吸越来越困难", "越来越喘", "喉咙发紧", "嘴唇肿",
    "胸痛", "胸口压榨样疼", "突然说话含糊", "说话含糊", "意识模糊", "神志不清",
    "肢体无力", "单侧无力", "单侧肢体无力", "右边胳膊抬不起来", "一侧胳膊抬不起来",
    "一边手脚没力", "嘴角歪", "突发剧烈头痛", "持续高热", "跌倒后疼痛", "想自杀",
    "不想活", "自伤",
]
SYMPTOM_TERMS = ["咳嗽", "发热", "喉咙痛", "咽喉痛", "鼻塞", "头晕", "胸闷", "胸痛", "气短"]
MEDICATION_TERMS = ["布洛芬", "氯沙坦", "二甲双胍", "降压药", "新开的药"]
NEGATION_MARKERS = ["没有", "无", "否认", "未出现", "不伴", "并无"]
NEGATABLE_TERMS = sorted(set(CRISIS_TERMS + SYMPTOM_TERMS), key=len, reverse=True)


def structure_record(payload: StructuringRequest) -> StructuringResponse:
    text = payload.text
    crisis = _affirmed_terms(text, CRISIS_TERMS)
    dosage_request = _is_dosage_request(text)

    if crisis:
        state = SafetyState.escalated
        report_type = "危急症状"
        message = (
            "记录包含可能需要立即处理的危险信号。系统不判断病情严重程度，"
            "应立即联系急救或就近急诊，并携带相关药物包装和原始记录。"
        )
        category = "crisis_signal"
        missing = ["药物名称", "过敏史核对", "当前症状和意识状态"]
    elif dosage_request:
        state = SafetyState.refused
        report_type = "用药安全请求"
        message = (
            "这条记录涉及用药剂量调整。系统不提供具体加量、减量、停药或补服建议。"
            "请按原医嘱或药品说明处理，并联系医生或药师确认。"
        )
        category = "medication_adjustment_request"
        missing = ["原始医嘱", "药物规格", "连续症状或血压记录"]
    else:
        state = SafetyState.passed
        category = "information_organization"
        if payload.input_mode == "blood_pressure" or "血压" in text:
            report_type = "血压记录"
            missing = ["测量姿势", "是否重复测量", "晚间复测值"]
        elif payload.input_mode == "ocr":
            report_type = "体检/化验单 OCR"
            missing = ["异常项目参考范围", "检查机构", "原报告逐项核对"]
        elif _affirmed_terms(text, SYMPTOM_TERMS):
            report_type = "症状记录"
            missing = ["开始时间", "药物剂量", "近期接触史"]
        else:
            report_type = "家庭健康记录"
            missing = ["开始时间", "相关药物", "后续计划"]
        message = (
            "已整理为可复核的家庭健康记录。该摘要只用于信息组织和复诊沟通准备，"
            "不提供诊断、处方或用药调整建议。"
        )

    symptoms = [_symptom_fact(text, term) for term in _affirmed_terms(text, SYMPTOM_TERMS)]
    medications = [_medication_fact(text, term) for term in _affirmed_terms(text, MEDICATION_TERMS)]
    allergies = [term for term in ["青霉素过敏", "药物过敏史待核对"] if term in text]
    if crisis and "药" in text and not medications:
        medications.append(_medication_fact(text, "药"))
    observations = _extract_observations(text)
    appointments = _extract_appointments(text)
    summary = _summary(report_type, message, symptoms, medications, observations)
    candidate = CanonicalRecord(
        report_type=report_type,
        event_date=payload.event_date,
        summary=summary,
        symptoms=symptoms,
        medications=medications,
        allergies=allergies,
        observations=observations,
        appointments=appointments,
        missing_fields=missing,
        safety=SafetyFact(
            state=state,
            category=category,
            message=message,
            unsafe_request_detected=dosage_request,
            forbidden_advice_generated=0,
        ),
    )
    return StructuringResponse(
        report_type=report_type,
        safety=state,
        symptoms=[item.text for item in symptoms],
        medications=[item.name for item in medications],
        allergies=allergies,
        missing_fields=missing,
        visit_summary=summary,
        unsafe_request_detected=dosage_request,
        forbidden_advice_generated=0,
        candidate=candidate,
    )


def _is_dosage_request(text: str) -> bool:
    asks_for_action = any(term in text for term in ["能不能", "可以不可以", "要不要", "怎么吃", "是否可以"])
    dosage_terms = _affirmed_terms(text, ["加倍", "两片", "补回来", "多吃", "减量", "停药"])
    return asks_for_action and bool(dosage_terms)


def _affirmed_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _is_affirmed(text, term)]


def _is_affirmed(text: str, term: str) -> bool:
    for match in re.finditer(re.escape(term), text):
        clause_start = max(
            text.rfind(mark, 0, match.start())
            for mark in ["。", "！", "？", "；", "，", ",", "\n", "但", "不过"]
        )
        prefix = text[clause_start + 1 : match.start()]
        suffix = text[match.end() : match.end() + 8]
        if _is_locally_negated(prefix):
            continue
        if _is_hypothetical_future(prefix):
            continue
        if "正常" in suffix or "无异常" in suffix:
            continue
        return True
    return False


def _is_locally_negated(prefix: str) -> bool:
    markers = "|".join(re.escape(item) for item in sorted(NEGATION_MARKERS, key=len, reverse=True))
    coordinator = r"(?:(?:也|仍|还)\s*)?"
    modifiers = r"(?:(?:出现|有)\s*)?(?:(?:明显|持续|任何|突然)\s*)?"
    if re.search(rf"{coordinator}(?:{markers})\s*{modifiers}$", prefix):
        return True

    terms = "|".join(re.escape(item) for item in NEGATABLE_TERMS)
    connector = r"(?:、|和|及|或|与)"
    coordinated = rf"{coordinator}(?:{markers})\s*{modifiers}(?:{terms})(?:\s*{connector}\s*(?:{terms}))*\s*{connector}\s*$"
    return re.search(coordinated, prefix) is not None


def _is_hypothetical_future(prefix: str) -> bool:
    """Ignore a crisis term scoped only under an explicit future condition."""
    return re.search(r"(?:如果|若|万一)[^。！？；]{0,36}(?:以后|将来|未来)?[^。！？；]{0,36}$", prefix) is not None


def _locator(text: str, term: str) -> SourceLocator:
    start = text.find(term)
    if start < 0:
        return SourceLocator()
    return SourceLocator(start=start, end=start + len(term))


def _symptom_fact(text: str, term: str) -> SymptomFact:
    return SymptomFact(text=term, source_locator=_locator(text, term))


def _medication_fact(text: str, term: str) -> MedicationFact:
    event_type = "missed" if "忘" in text or "漏服" in text else "reported"
    return MedicationFact(name=term, event_type=event_type, source_locator=_locator(text, term))


def _extract_observations(text: str) -> list[ObservationFact]:
    observations: list[ObservationFact] = []
    blood_pressure = re.search(r"血压\s*(\d{2,3})\s*/\s*(\d{2,3})", text)
    if blood_pressure:
        observations.append(ObservationFact(
            name="血压", value=f"{blood_pressure.group(1)}/{blood_pressure.group(2)}",
            unit="mmHg",
            source_locator=SourceLocator(start=blood_pressure.start(), end=blood_pressure.end()),
        ))
    heart_rate = re.search(r"心率\s*(\d{2,3})", text)
    if heart_rate:
        observations.append(ObservationFact(
            name="心率", value=heart_rate.group(1), unit="bpm",
            source_locator=SourceLocator(start=heart_rate.start(), end=heart_rate.end()),
        ))
    for name in ["空腹血糖", "总胆固醇", "低密度脂蛋白"]:
        match = re.search(rf"{name}\s*(\d+(?:\.\d+)?)\s*(mmol/L)?", text)
        if match:
            observations.append(ObservationFact(
                name=name, value=match.group(1), unit=match.group(2) or "",
                source_locator=SourceLocator(start=match.start(), end=match.end()),
            ))
    return observations


def _extract_appointments(text: str) -> list[AppointmentFact]:
    terms = [term for term in ["社区门诊", "复诊", "急诊"] if term in text]
    return [AppointmentFact(text=term, source_locator=_locator(text, term)) for term in terms]


def _summary(
    report_type: str,
    safety_message: str,
    symptoms: list[SymptomFact],
    medications: list[MedicationFact],
    observations: list[ObservationFact],
) -> str:
    facts: list[str] = []
    if symptoms:
        facts.append("症状：" + "、".join(item.text for item in symptoms))
    if medications:
        facts.append("记录用药：" + "、".join(item.name for item in medications))
    if observations:
        facts.append("测量：" + "、".join(f"{item.name} {item.value}{item.unit}" for item in observations))
    fact_text = "；".join(facts) if facts else "尚无可确认的结构化事实"
    return f"{report_type}。{fact_text}。{safety_message}"
