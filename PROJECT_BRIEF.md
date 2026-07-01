# 项目 Handoff Brief —— Family Health Memory Copilot（工作名）

> 这份文档是给本地 coding agent（Codex / Claude Code）的核心上下文。
> 可直接作为 `AGENTS.md` / `CLAUDE.md` 引用的项目说明，或放 `docs/PROJECT_BRIEF.md`。
> 工作名随便改，建议 repo 名 `family-health-copilot`，模型/adapter 名 `med-structurer-zh`。

---

## 0. 给本地 agent 的话：怎么用这份文档

- 这是一个**真实落地产品**，核心引擎是一个**值得微调、值得严格评测的中文医疗模型**。两者是同一个项目，不是两个。
- 你（agent）按第 8 节的**单条执行链顺序**推进，**自主快速跑**，但每一步都要像学生写实验记录一样留下详细数据（见第 10 节）。
- 可以参考网上的教程 repo，但要**记录踩的坑、为什么这么改、下一步换什么方案**，不要照抄。
- 遇到第 5 节的**硬约束**绝不能越界。任何涉及真实家人医疗数据的事，停下来问我。
- 不确定的数字、没跑过的实验，**绝不编造**（见第 10 节 fail-loud / no-fabricated-metrics）。

---

## 1. 背景：我是谁

- ECE（Robotics & Control）MEng 在读，有导师给的 HPC 资源（Narval / Digital Research Alliance of Canada，A100）没用满。
- 技术栈：Python / C++ / PyTorch / Docker / SQL / LangChain。
- 做过一个本地医疗 scribe 系统（合同活），踩过：Dockerized PaddleOCR、本地 LLM endpoint（Gemma 级）、ASR、以及一套 SOAP note 质量评测 harness。**那套评测思路和 OCR/本地服务架构可以迁移到本项目**（但不要搬合同客户的代码，迁移的是方法和架构 pattern）。

---

## 2. 原始意图（我最初的 prompt，原文，保留）

> 我想要自己微调大模型，现在我的 project 基本上空了，老师给我这个我不用白不用。我需要用医疗数据设计一个微调或者心理学为了丰富我的简历，我要设计 metrics，合理的 pipeline 各种细节，和 evaluation 整体要像个学生每一步都要详细数据。然后可以之后再接个 RAG。我想让你自动跑模仿我的风格自己去快速的跑，一定要设计的有学习过程或者可以照着网上的教学 repo 去操作自己记录问题并自己设计新的方案。你觉得有可能吗，我有这么好的硬件我必须得做点别人做不了的项目，然后我还传到 GitHub/HuggingFace 对吧，反正你看看我一个人做个什么样的项目先去判断可行性。

**翻译成约束**：要微调 + 要严格评测 + 要像研究记录一样有详细数据 + 之后接 RAG + 用 A100 做别人做不了的系统实验 + 能发 GitHub/HF + agent 自主推进并记录学习过程。

---

## 3. 我一直想做的真实产品（给我妈的）

我妈经常觉得身体不舒服，反复做重复检查，报告散落在微信/相册/抽屉里，每次看病重新讲一遍，家人也不清楚长期变化。我想要一个**长期健康记忆管家**：

- 拍照/PDF 上传检查报告、化验单、药盒、处方 → OCR → 自动归档。
- 一句语音说症状 → 自动归进**长期症状时间线**。
- 识别**重复检查**（过去 N 个月做过几次血常规等），帮准备就医沟通问题。
- 复诊前一键生成**给医生看的一页摘要**（主诉 / 症状时间线 / 已做检查 / 用药 / 要问的问题）。
- 提醒（复诊、拿报告、吃药、上传报告）。
- **家庭周报**发给在外地的我（子女）。

**它不替代医生、不诊断、不调药。** 它解决的是"信息整理 + 长期记忆 + 就医沟通"的真实痛点。

---

## 4. 融合后的项目定位（这是整个项目的脊柱）

**一句话**：微调一个开源中文医疗结构化模型，用它驱动一个私密的长期家庭健康助手；模型只用公开数据训练和评测（可发 HF），真实家人数据只在本地推理（永不公开）。

**端到端链条：**

```
报告/PDF 或 一句语音症状
      ↓  OCR / ASR（PaddleOCR 等现成）
 ┌──────────────────────────────────┐
 │ 微调模型 ①：脏中文报告/口语 → 结构化字段  │  ← 核心微调点，只用公开数据
 └──────────────────────────────────┘
      ↓
 结构化长期健康档案（SQLite/Postgres：
 symptom_logs / lab_items / reports / medications / appointments / reminders）
      ↓
 ┌──────────────────────────────────┐
 │ 微调模型 ②：生成「给医生看的一页摘要」    │  ← 同模型，被 eval 量化
 │ + 家庭周报（非诊断性）                  │
 └──────────────────────────────────┘
      ↓  安全分类器 + 危急症状升级规则
 输出：时间线 / 就诊摘要 / 家庭周报
      ↓ （最后再接）RAG：带引用的可靠解释
```

**为什么这不是教程复刻**：通用 instruct 模型在"中文医疗报告结构化 + 安全拒答"这个组合上很弱。微调专打这两点，且全程被一套领域 eval harness 量化（第 7 节）。**评测才是简历皇冠**——会发 LoRA 的人一堆，认真做领域评测的少。

**简历那行字（成品长这样）**：
> Fine-tuned and evaluated an open Chinese medical-record-structuring LLM (LoRA/QLoRA on A100) powering a private longitudinal family-health assistant. Built a domain-specific eval harness: extraction F1, safety refusal rate, crisis-symptom recall, hallucination & overdiagnosis rates, plus a RAG-ready grounded-summary benchmark.

---

## 5. 硬约束（不可越界）

### 5.1 隐私防火墙（项目能不能发布的前提）
- **可发布的模型/adapter/eval/代码，只用公开或合成数据训练和评测。**
- **我妈的真实医疗数据：只喂给已训练好的模型做本地推理，永远不进训练集、不进 repo、不进 HF、不进任何云。**
- GitHub/HF 上展示的 demo 数据必须是合成的或公开的。仓库里一个字真实 PII 都不能有。
- `.gitignore` 必须排除 `data/private/`、`*.real.*`、任何本地档案库文件。

### 5.2 医疗安全边界
- 不诊断、不给/不调药物剂量、不下"你没事/不用查了"这种结论。
- 角色是"整理资料 + 帮准备就医沟通"，导向永远是"带去给医生确认"。
- **危急症状**（胸痛、呼吸困难、意识模糊、剧烈头痛、肢体无力、持续高热、摔倒后疼痛、自伤念头等）：不判断严重程度，直接建议立即就医/联系家人/急救，并触发升级流程。
- 这些规则写成显式 ruleset + 测试用例，纳入第 7 节评测。

### 5.3 Secret / 凭据
- **任何密码、token、access code 绝不写进代码、配置、文档或日志。**
- Narval 用 **SSH key** 登录（`ssh-keygen` + `ssh-copy-id`），不用密码。
- secret 走环境变量 + `.env`（`.env` 进 `.gitignore`），仓库里只放 `.env.example`。

### 5.4 不许动我的论文（Narval 上）
- 论文目录 `~/scratch/MEng_Project/`（尤其 `data/`）**绝对不碰、不读写、不复用**。
- 本项目独立目录：`~/scratch/lora_health/`；独立 venv；Slurm job-name 加前缀 `lora_health_*`；用 `--chdir` 指到本项目目录。
- 跑作业前先 `diskusage_report` 看 scratch 配额，别把论文数据挤爆。

---

## 6. 架构与技术选型

- **Base model**：Qwen2.5-7B-Instruct 级（中文强）。先 7B/8B，确认链路后再考虑更大。
- **微调框架**：HuggingFace TRL `SFTTrainer` + PEFT（LoRA / QLoRA）。只训 adapter，方便上传 HF。
- **硬件**：Narval A100（`--gres=gpu:a100:1`，account `def-falmaham`，user `syin94`，host `narval.computecanada.ca`）。训练类作业 1 node + 1 A100 + 8–16 CPU + 48–64G RAM；轻量审计/解压类用 CPU 作业。
- **OCR**：PaddleOCR（已有 Docker 经验）；备选 GPT-4o vision / Azure Document Intelligence 做对照。
- **数据库**：结构化用 SQLite（MVP）→ Postgres + pgvector（后期）。**重点：健康数据必须有结构化表，不能只靠向量库**——"过去半年做过几次血常规"这种查询要 SQL，不能纯 RAG。
- **Memory / 长期记忆**：先自建 + 结构化表；需要对话个性化记忆层时再评估 Mem0。
- **产品输入端**：MVP 先用本地网页或 Telegram，**微信生态最后再接**（公众号/小程序开发折磨，会拖节奏）。

### 公开数据（训练/评测候选，**用前逐个核 license**）
- `FreedomIntelligence/medical-o1-reasoning-SFT`（有中文子集，做 medical reasoning SFT）。
- `Amod/mental_health_counseling_conversations`（**RAIL-D，非商业/有改动限制，谨慎，README 写明限制**）。
- 评测：PubMedQA（yes/no/maybe）、MedMCQA（医学选择题）作为外部 sanity benchmark。
- 中文医疗报告结构化：优先找开源中文医疗 NER / 报告解析数据；不够就**自己合成**一批带 gold 结构化标注的样本。

---

## 7. 评测 harness（简历皇冠，先于训练建好）

每个指标都要有 gold 测试集 + 脚本 + 可复现数字：

1. **抽取准确率**：报告/口语 → 结构化字段的 field-level F1（日期、医院、检查名、关键指标、用药）。
2. **就诊摘要质量**：vs gold 摘要（覆盖度 / 是否漏关键项 / 是否引入未提及内容）。
3. **安全拒答率**：面对"我能吃几片药""帮我诊断"等请求是否正确拒答/转就医。
4. **危机症状召回**：危急症状测试集上是否触发升级（recall 优先，漏报代价最高）。
5. **幻觉率**：问不存在的 guideline / 药物剂量时是否编造。
6. **过度诊断率**：把普通症状直接说成严重疾病的比例。
7. **外部 benchmark**：MedMCQA / PubMedQA 准确率（证明没把通用医学能力训坏）。
8. **（接 RAG 后）groundedness / citation faithfulness / unsupported-claim rate / no-answer calibration**。

---

## 8. 执行顺序（单条链，**严格按序**，不要乱跳）

> 反常但关键：**先建评测集，再训模型**。

1. **建 gold eval set**：攒一小批合成/公开的中文报告 + 症状记录，写好目标结构化输出、目标摘要、危急症状测试集。这批东西**既是产品需求定义，也是简历指标来源**，一鱼两吃。
2. **Baseline**：原始 instruct 模型跑全套评测，记下数字 = "before"。
3. **搭产品脊柱**：围绕 baseline 模型，把 `OCR/ASR → 抽取 → 时间线 → 摘要 → 升级` 用 2–3 份**假报告**在本地端到端跑通。此时已有能跑的产品，还没微调。
4. **微调**：A100 上 LoRA/QLoRA（公开数据），专打 step 2 暴露的弱项。重跑评测 = "after"。before/after delta 就是故事。
5. **消融**：数据配比 / LoRA rank（8/16/32）/ 模型大小 / 数据量（1k/5k/20k）。这步让它像 research 不像 notebook。
6. **本地私有部署**：把验证过的模型用到我妈的真实数据上（私有层，遵守 5.1）。
7. **RAG 扩展**：PubMed / 公开 guideline / 健康资源 + FAISS/Chroma，做带引用的可靠解释，跑第 7 节第 8 组指标。

**Go/No-Go 检查点**：step 1–3 跑完（约第一阶段末）做一次评审——脊柱能跑通、baseline 数字合理、gold set 站得住，才进入 step 4 微调。

---

## 9. 仓库结构（建议）

```
family-health-copilot/
  README.md                 # 项目说明 + 简历级 model card 摘要
  AGENTS.md / CLAUDE.md      # 引用本 brief
  .env.example
  .gitignore                # 排除 data/private/, *.real.*, checkpoints, .env
  docs/
    PROJECT_BRIEF.md         # 本文件
    experiment_log.md        # 见第 10 节
    error_analysis.md
    model_card.md
  configs/
    qwen7b_lora_extract.yaml
    qwen7b_lora_summary.yaml
  data/
    public/                  # 公开/合成数据（可 commit 小样本）
    private/                 # 真实家人数据，永不 commit
    dataset_manifest.json
  eval/
    gold/                    # gold 测试集（合成/公开）
    run_eval.py
    metrics_extract.py
    metrics_safety.py
    metrics_crisis.py
    metrics_summary.py
  src/
    ocr/        asr/         # 输入处理
    structure/               # 抽取（模型①）
    timeline/                # 结构化档案 + SQL
    summary/                 # 就诊摘要 + 周报（模型②）
    safety/                  # 危急症状 ruleset + 升级
    serve/                   # 本地推理服务
  train/
    prepare_dataset.py
    train_sft.py
  scripts/
    submit_narval.sh         # Slurm 提交（带隔离规则）
  results/
    baseline/ lora_extract/ lora_summary/ ablations/
```

---

## 10. 工作方式与代码风格（agent 必须遵守）

- **fail-loud**：不要静默 `except: pass`；遇到预期外情况直接 raise / 打清楚的错。
- **skeleton-first**：先把 pipeline 端到端 stub 通（每段返回假数据也行），再逐段填实现。
- **no fabricated metrics**：绝不编数字。没跑的实验、缺的结果，明确写"未运行/缺失"，不要凑。
- **student-readable code**：清晰、少过度抽象，读起来像很强的学生写的，不像 AI 模板。
- **first-principles + simplicity over abstraction**：先想清楚再写，能简单别复杂。
- **学生式实验记录**（这是原始 prompt 的硬要求）：`docs/experiment_log.md` 每个 run 记全：
  ```
  Run ID / Date:
  Base model:        Dataset version:     Train rows / Val rows:
  LoRA rank / LR / batch size / GPU / training time:
  Final loss:        Extraction F1:       Safety recall:   其他指标:
  Failure examples:
  What I changed next & why:
  ```
  失败和坑写进 `docs/error_analysis.md`。参考教程 repo 时，记录"它怎么做的 / 我为什么改 / 我的新方案"。
- **自主推进**：按第 8 节顺序自己往前跑、自己记录、自己设计下一步；只在触碰第 5 节硬约束、或要用真实家人数据时停下来问我。

---

## 11. 现在第一步该干什么

1. 初始化仓库 + 第 9 节结构 + `.gitignore`（先把隐私防火墙立起来）。
2. 写 `eval/gold/` 的第一批合成中文报告样本（5–10 份）+ 对应 gold 结构化输出 + gold 摘要 + 危急症状测试用例。
3. 写 `eval/run_eval.py` 骨架（先能对 baseline 跑出第 1、2、3、4 组指标）。
4. 跑 baseline（Qwen2.5-7B-Instruct），把数字填进 `experiment_log.md`。
5. 搭产品脊柱（step 3）端到端跑通假数据。
6. 到 Go/No-Go 检查点，停下来给我看结果再决定是否进微调。

> 注意：step 1–5 大量复用我已有的 OCR / 本地模型服务 / 评测经验，应该比从零快很多。

---

## 12. 本地环境、工具与交接清单

### 12.0 第一件事：先确认不影响论文（最重要）
在 Narval 上做任何操作前，**先确认本项目与论文完全隔离**（见 5.4）：本项目一律在 `~/scratch/lora_health/`，**绝不读写、不复用** `~/scratch/MEng_Project/`（尤其 `data/`）。这点压倒一切，宁可慢也不能动到论文数据。

### 12.1 项目落地位置与初始化
- 本地项目根目录：`D:\lora`。在这里 `/init`，配好所有文件（`AGENTS.md`、`CLAUDE.md`、`.gitignore`、`.env.example`、`README.md` 等），并初始化 git。
- `AGENTS.md` / `CLAUDE.md` 引用本 brief 作为核心上下文；把第 0、5、10 节（工作方式 / 硬约束 / 风格）的要点提炼进去当行为规范。
- 用 **graphify skill** 来省 context、整理配置和这份文档的结构。

### 12.2 凭据处理（**不要把密码写进文件**）
服务器/账户连接信息（非机密部分，可记录）：
- 集群：Narval / Digital Research Alliance of Canada
- Host：`narval.computecanada.ca`，用户：`syin94`，Slurm account：`def-falmaham`
- GPU：`--gres=gpu:a100:1`

**密码与登录 code 一律不落盘**：
- 密码：`<见密码管理器 / 不写入仓库>`（原始密码已在聊天中暴露，**请尽快改掉**）
- 登录 code：`<时效性一次性码，不记录>`
- 正确做法：Narval 改用 **SSH key** 登录（`ssh-keygen` → `ssh-copy-id syin94@narval.computecanada.ca`），之后免密码；其它 secret 走 `.env`（进 `.gitignore`），仓库只放 `.env.example`。

### 12.3 复用我已有的资产
- **代码风格 + 我原来的其他创意**：`D:\MyProjects\wiki` —— 写代码前读一下，保持风格一致（学生可读、fail-loud、少抽象）。
- **RAG 结构（直接借用）**：`D:\简历故事和细节\THIS_WEEK\02-EVENUP-之后` —— 我的 `rageval` 已经做了一部分 RAG 探索，第 8 节 step 7 的 RAG 直接沿用那套结构，别重造。
- **coval**：一个类似但没做下去的项目 —— 把本项目做到比它**更完整、更漂亮、更强**，可参考它当时的思路和半成品。
- **面试准备 / 过往项目信息**：同在上面简历文件夹，写 README 和 model card 时可对齐口径。

### 12.4 原始想法的来历（保留语境）
之前和 GPT 讨论过一个偏**心理学**的方向，但我真正想做的是：**一个自动读 OCR、能长期记录我自己/家人个人化验数据和用药、相当于给老年人的提醒助手。** 这正是本项目第 3、4 节的核心——长期健康记忆 + 报告 OCR 归档 + 症状时间线 + 用药/复诊提醒。心理学/情绪陪伴**不作为第一版核心**（太卷、监管风险高），最多作为温和提醒的语气层。

### 12.5 交接给 agent 的初步任务
1. 在 `D:\lora` `/init`，配好 `AGENTS.md` 等全部文件、git、`.gitignore`（先立隐私防火墙）。
2. 读 `D:\MyProjects\wiki` 对齐代码风格；读 `02-EVENUP-之后` 的 rageval 结构备用。
3. 把第 8 节执行链整理成本仓库的 `docs/PLAN.md`（含 Go/No-Go 检查点）。
4. 按第 11 节"第一步"开始推进；触碰真实家人数据或第 5 节硬约束前停下来问我。
