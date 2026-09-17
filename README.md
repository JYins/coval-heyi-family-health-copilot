# Coval HeYi · 家庭健康记忆 / Family Health Memory

一个把零散健康信息变成**可核对、可追溯的长期记录**的本地产品原型。它帮助家人整理症状、血压和就诊资料，在下次看医生前准备摘要；它**不诊断、不推荐用药，也不能替代医生**。

A local prototype that turns scattered health notes into a **reviewable, traceable family timeline** and a doctor-facing visit brief. It does **not** diagnose, prescribe, or replace a clinician.

> **当前边界 / Current boundary:** 公开版只供合成或公开示例演示。**请勿输入真实家庭或患者资料。** 真实数据所需的加密、身份验证和删除机制尚未通过门禁。
>
> The public build is for synthetic/public examples only. **Do not enter real family or patient data.**

![桌面端：先核对，再保存到健康记忆 / Desktop: review before save](docs/assets/coval-heyi-desktop.png)

<img src="docs/assets/coval-heyi-mobile.png" alt="手机端：合成数据的新建记录流程 / Mobile synthetic new-record flow" width="310" />

截图来自浏览器中的合成数据流程；OCR、语音、每日血压和家庭周报等入口不等于这些能力已经全部上线。

Both screenshots show the synthetic demo, not real patient data or a completed OCR/ASR service.

## 中文：我想解决什么问题

一次就诊留下的报告、口头症状、血压数字和药物信息，往往散落在不同地方。下次复诊时，家人需要重新拼凑时间线。Coval HeYi 的目标是做一个家庭自己掌控的“健康记忆”：**先保存原话和来源，再用模型整理成候选事实，由人确认后才写入长期记录**。最后用这些已确认的信息准备给医生看的摘要和待问问题，而不是让聊天机器人猜诊断。

我把它同时当成产品和研究项目。产品要能在失败、重启、误点和重复提交时保住记录；模型要有可重复的评测，只有在安全和质量门禁通过时才能成为默认能力。

### 今天真正能做的事

1. 在本地网页录入**虚构**的家庭成员、症状、血压或文字记录。原文先进入 SQLite；推理失败后仍能从待处理列表恢复。
2. 查看和修改结构化候选内容；未确认的候选不会进入正式健康时间线。保存后可再编辑、查看版本、撤销到旧内容（撤销也新增版本，不抹掉历史）。
3. 生成非诊断性的就诊摘要、待补信息和安全提示。确定性规则负责危急症状升级和部分用药边界，模型不能覆盖这些规则。
4. 用命令行对**合成演示数据库**做校验、备份、干净路径恢复，以及保守的 FHIR R4 文档 Bundle 导出。备份**未加密、未签名**，不能用于真实医疗资料。

实现链条：`Next.js 页面 → FastAPI → 原文/来源持久化 → 本地推理 provider → 家人核对 → SQLite 版本化时间线 → 就诊摘要/安全提示`。默认 provider 是明确标注的 `mock-rules-v2`，不是微调模型。[当前能力清单](docs/CURRENT_STATE.md)列出每一项的证据和限制。

### 为什么这样设计

| 决策 | 解决的问题 | 证据 |
| --- | --- | --- |
| 先存原文，再做推理 | 模型失败也不丢输入；租约和版本检查挡住并发重试、过期结果 | [ADR 0001](docs/adr/0001-capture-first-leased-processing.md) |
| 人确认后才进时间线 | 机器提取结果只是候选；修改和撤销都留痕 | [ADR 0002](docs/adr/0002-review-before-canonical-memory.md) |
| 安全规则与模型分层 | 候选模型接上了，也不代表可以上线 | [ADR 0003](docs/adr/0003-model-gates-over-model-optimism.md) |
| 备份不等于隐私保护 | 校验和恢复已测；未加密的 v1 包仍禁止真实数据 | [ADR 0004](docs/adr/0004-vault-v1-is-portability-not-privacy.md) |

### 微调到底做出了什么

使用 `Qwen/Qwen2.5-7B-Instruct` 做过一次小样本 LoRA SFT v2：**20 条人工合成训练样本、6 条验证样本，3 个优化步骤**。历史本地实验中，适配器通过 provider 接入 API、浏览器和 SQLite；当前默认仍是 mock。重新启用本地模型还需要核对完整模型及适配器文件身份。实验的“断网”是离线环境变量、只读本地模型路径及阻止非本机网络的 socket guard，**不是真拔网线**。

更重要的是，上线门禁**拒绝了**这个候选。生产调用形态下，三个定向合成切片的抽取 F1（基础模型 → LoRA）为 `0.6767→0.6767`、`0.6897→0.6897`、`0.6939→0.6222`。另一个盲确认集里，基础模型与适配器都把 16 个无需拒答案例中的 8 个误拒；适配器在 5 个安全对抗案例中又误拒 1 个。早期更好看的数字受评测标签泄漏影响，已在实验记录中更正。**结论不是“LoRA 提升了医疗能力”，而是“接入成功，但证据不支持把它设为默认”。** [本地推理报告](docs/PHASE_2_LOCAL_INFERENCE.md) · [产品形态复评](docs/PHASE_2B_SAFETY_INTENT.md) · [公开证据清单](docs/CLAIM_LEDGER.md)

### 本地试用（Windows PowerShell，合成数据）

环境：Python 3.12、Node.js 22；CI 在 Linux 上运行后端/前端测试。初次安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd apps\coval-health-web
npm.cmd ci
```

在仓库根目录开两个终端：

```powershell
# 终端 1：API
.\.venv\Scripts\python.exe -m uvicorn src.serve.coval_health_api:app --host 127.0.0.1 --port 8000
```

```powershell
# 终端 2：网页
cd apps\coval-health-web
npm.cmd run dev
```

打开 `http://127.0.0.1:3000`。默认数据库在被 Git 忽略的 `data/local/coval_health.sqlite`。网页要求确认“仅限虚构/公开数据”；这只是防误用提示，**不能自动识别并阻止真实资料**。API 不可用时，页面会显示错误并禁用持久化写入。完整测试入口：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_local_quality.ps1
```

该脚本覆盖后端/API、前端 lint/类型/构建和浏览器 E2E；可用 `-Install` 安装依赖，或用 `-SkipBrowser` 跳过浏览器。备份/恢复命令和限制见 [架构与运行说明](docs/ARCHITECTURE.md)和 [vault ADR](docs/adr/0004-vault-v1-is-portability-not-privacy.md)。

### 还没有做完的事

- 真实照片/PDF OCR、语音 ASR、提醒 worker、家庭周报 worker 和医生 PDF；界面中的相关入口目前是设计/占位，不是交付承诺。
- 面向真实家庭资料的完整数据库及 WAL 加密、密钥托管与恢复、认证、加密备份、可验证删除，以及固定安全的 SQLite 运行时。[威胁模型](docs/THREAT_MODEL.md)和 `COVAL_REAL_DATA_MODE=1` 的 fail-closed 门禁会阻止提前宣称可用。
- RAG 目前只有 7 篇片段、8 个查询的检索冒烟测试；不是成熟的医学问答。GGUF/llama.cpp 也只有接口，未完成实际部署和基准测试。

## English: the product and the engineering story

Health information accumulates in reports, conversations, home measurements, and scattered notes. Coval HeYi aims to give a family a durable, locally controlled memory of **what was actually recorded, when, and from which source**. The workflow preserves the original text first, proposes structured facts, asks a person to review them, and only then adds them to the timeline. Its doctor-facing brief is for preparing a visit, not for medical decisions.

The interesting engineering choice is that the model is replaceable, but the memory and safety contracts are not. Capture survives provider failure; leases and compare-and-swap checks reject stale retries; sources are immutable; approval, edits, and undo produce append-only versions. A deterministic safety layer can escalate, while an unapproved model candidate cannot silently become the product default. The local vault is tested for integrity and restore, but explicitly remains **unencrypted**.

The LoRA work is a measured negative result, not a claim of clinical improvement. A Qwen2.5-7B LoRA v2 adapter was trained on 20 synthetic training rows, with 6 validation rows, and integrated in a historical local provider run. Re-enabling a local model requires pinned full-file model and adapter identity. Synthetic, product-shaped evaluation found no extraction gain on two slices, a regression on one, and unacceptable false refusals; a later prompt candidate also failed. The default remains the labeled deterministic `mock-rules-v2` provider. The earlier attractive scores were corrected after discovering prompt-context leakage. See the [experiment log](docs/experiment_log.md), [error analysis](docs/error_analysis.md), and [model evidence](docs/PHASE_2B_SAFETY_INTENT.md).

For a quick synthetic demo, use the PowerShell commands above. For technical review, start with the [90-second demo script](docs/DEMO_90S.md), [current-state matrix](docs/CURRENT_STATE.md), [architecture](docs/ARCHITECTURE.md), [threat model](docs/THREAT_MODEL.md), and [claim ledger](docs/CLAIM_LEDGER.md). The CI workflow runs backend, frontend, and Chromium browser checks; passing tests demonstrate the synthetic prototype, **not** clinical safety or readiness for real family data.

**Resume-safe description:** Built a synthetic-only local family-health memory prototype with immutable source provenance, capture-first recovery, review-before-save, append-only versions, tested backup/restore, deterministic safety controls, conservative FHIR R4 export, and evaluation gates that rejected unsafe model candidates.

## Repository map / 仓库导览

- `apps/coval-health-web/` — Next.js 界面 / family-facing web UI.
- `src/serve/`, `src/health_memory/` — FastAPI、SQLite、迁移和版本化记忆 / API and durable memory.
- `eval/`, `train/`, `artifacts/public/` — 合成评测、训练入口和公开证据 / synthetic evaluation, training entry points, and curated receipts.
- `docs/` — 决策记录、实验日志、错误分析、威胁模型 / design decisions, lab notes, failure analysis, and privacy gates.

公开演示和评测只用合成/公开安全数据；不要提交密钥、真实家庭资料、数据库、模型权重或本地研究输出。

The demos and evaluations use synthetic/public-safe data only. No open-source license is granted yet; contact the author before reusing code or assets.
