# Coval Health WebApp Packaging Plan

## Goal

Package the Chinese medical structuring LoRA project as a product-shaped demo instead of only a training/eval repository.

The product story:

> Coval started as relationship memory: one person, many context fragments, retrieval, briefing, and feedback. Coval Health is the health-memory variant: one family member, many medical records, structured timeline, visit-prep communication summary, safety escalation, and model-evaluation evidence.

This should make the project readable to recruiters as both:

- a real AI product surface; and
- a serious model/evaluation project under the hood.

## Existing Assets

### Coval

Path: `D:\MyProjects\coco\coval`

Current shape:

- FastAPI backend
- auth/JWT
- PostgreSQL-style persistence
- Qdrant/vector-store pattern
- prompt assembly flow
- Next.js frontend under `web/`
- existing `docs/medical_profile_design.md` already describes a future medical variant

### LoRA Health

Path: `D:\lora`

Current shape:

- synthetic/public-safe gold evals
- Qwen2.5-7B-Instruct base model
- SFT v1 LoRA adapter on Narval
- deterministic normalization and report-type/template summaries
- JSON unit-value recovery
- fake-data product spine:
  - structured report rows
  - timeline DB
  - visit-prep communication summary
  - safety refusals
  - crisis escalations
- project gap and v1.1 gap reports

## Recommended Product Positioning

Working name:

- `Coval HeYi`
- English subtitle: `private family health memory`
- Chinese reading: `合医 / 和医 / 合忆`

Why this works:

- It keeps `Coval`, so the resume story remains continuous from relationship memory to health memory.
- `HeYi` feels like a bilingual product name rather than a literal translation.
- `合医` suggests organizing medical context for the doctor.
- `和医` suggests a calm, human-centered medical support posture.
- `合忆` connects back to Coval's memory theme: assembling fragmented family health memories.

Public-facing fallback:

- Use `Coval Health` when clarity matters.
- Use `Coval HeYi` as the branded product name in the UI and portfolio story.

Do not market it as a diagnosis app.

Position it as:

- organizes Chinese family medical records;
- extracts structured facts from messy notes/reports;
- builds a longitudinal timeline;
- prepares visit-prep communication summaries for families to bring to care visits;
- flags medication-advice requests and crisis symptoms;
- proves behavior with eval metrics before claiming model improvement.

## MVP WebApp Shape

Build as a product demo first, not a full clinical system.

Suggested first route in Coval frontend:

```text
/health-demo
```

Main screen:

1. Family member switcher
   - demo-only members such as `Mom`, `Dad`, `Self`
   - all synthetic data

2. Upload/intake panel
   - text paste for a fake Chinese medical note
   - sample buttons for:
     - lab report
     - medication note
     - symptom note
     - unsafe medication request
     - crisis symptom

3. Structuring result
   - report type
   - date/hospital
   - medications
   - symptoms with onset
   - appointments
   - safety status

4. Health timeline
   - chronological cards or rows
   - record categories
   - safety markers

5. Visit-prep communication summary
   - concise Chinese family-facing summary for clinic conversations
   - clear disclaimer: organization only, not diagnosis/treatment

6. Evaluation sidebar
   - base model vs SFT/constrained metrics
   - v1.1 recovered extraction F1
   - safety refusal and crisis recall
   - hallucination/overdiagnosis rates

## Clinic / Phlox-Informed Product Features

The clinic work should influence the WebApp as product discipline, not as copied patient data or copied production UI.

Local evidence reviewed:

- `D:\clinic\2026-05-29_BOSS_REPORT.md`
- `D:\clinic\2026-05-31_BOSS_REPORT.md`
- Phlox workflow harness notes from 2026-06-03
- Amazon clinic project pack under `D:\简历故事和细节\amazon准备\project_packs\clinic_midtown_phlox`
- Phlox screenshots showing dashboard, note editor, background jobs, undo, apply, save, and service/status panels

### Feature 1: Workflow-First Intake

Clinic lesson:

- Phlox became stronger when it was treated as a workflow loop, not a single prompt.

Use in Coval HeYi:

```text
Capture -> Structure -> Review -> Save to timeline -> Verify / safety status -> Visit-prep summary
```

UI implication:

- The first screen should show the current workflow state.
- Avoid a generic chatbot box as the primary interface.

### Feature 2: Async Job Rail

Clinic lesson:

- Phlox async jobs return quickly, keep running in the background, survive refresh, and can attach results to the correct encounter.

Use in Coval HeYi:

- Show `Structuring`, `Safety check`, and `Visit-prep summary` as recoverable background jobs.
- Each job has:
  - status: queued, running, completed, failed, applied
  - elapsed time
  - retry
  - undo apply

UI implication:

- Add a compact bottom job drawer inspired by Phlox, but with a cleaner clinical style.

### Feature 3: Reviewed Note Before Structured Extraction

Clinic lesson:

- Safer architecture: unified reviewable family note first, then structured extraction after review.

Use in Coval HeYi:

- For demo:
  - show original Chinese note;
  - show model-structured fields;
  - show a reviewed summary surface;
  - only then let user commit the record to timeline.

UI implication:

- The center panel should be an editable/reviewable workspace, not a static JSON viewer.

### Feature 4: Verify Claims Panel

Clinic lesson:

- Phlox Verify flagged unsupported claims in a draft note, such as facts not present in the transcript.

Use in Coval HeYi:

- Add a right-side `Verification` panel:
  - unsupported claims: 0
  - forbidden advice: 0
  - safety gate: passed/refused/escalated
  - missing fields: symptom onset, medication dose, date

UI implication:

- This is the bridge between LoRA eval metrics and product trust.
- It makes the app feel medically serious without pretending to diagnose.

### Feature 5: Service/Model Health Strip

Clinic lesson:

- Local clinical AI systems need visible service health: LLM router, OCR, ASR, dashboard, Docker/systemd, Tailscale.

Use in Coval HeYi:

- Add a small status strip:
  - model: Qwen2.5-7B LoRA adapter
  - parser: JSON recovery enabled
  - eval gate: safety/crisis pass
  - data mode: synthetic/demo

UI implication:

- For the portfolio demo, this proves the project is operationally aware.
- Do not expose private hostnames, keys, IPs, or real service internals.

### Feature 6: Production/Test Boundary Badge

Clinic lesson:

- Keeping production 5000 separate from test 5001 was a major trust-building decision.

Use in Coval HeYi:

- Visible badge:
  - `Demo mode: synthetic records only`
  - `No real family data`
  - `No diagnosis or medication adjustment`

UI implication:

- This turns the privacy boundary into a product feature.

### Feature 7: OCR/ASR As Future Inputs

Clinic lesson:

- PaddleOCR, ASR, diarization, and local LLM endpoints are service integrations with health checks and failure behavior.

Use in Coval HeYi:

- In MVP, show OCR/ASR as disabled future input tabs:
  - paste text: enabled
  - upload report image: demo stub
  - voice symptom note: demo stub

UI implication:

- The page feels extensible without faking completed features.

## Why This Completes The Portfolio Story

Without the WebApp, this project looks like:

> I fine-tuned a model and ran metrics.

With Coval Health, it becomes:

> I built an evaluation-first AI product system: a private family health-memory app that uses a LoRA-tuned Chinese medical structuring model, validates safety behavior with synthetic/public evals, and plugs model outputs into a usable timeline and visit-prep workflow.

That is much stronger because it shows:

- model adaptation;
- eval discipline;
- safety boundaries;
- backend/product thinking;
- frontend demo ability;
- privacy-aware design.

## Architecture Bridge

```text
Coval core idea
  user -> person -> memory chunks -> retrieval -> briefing

Coval Health variant
  user -> family member -> medical records -> structured timeline -> visit-prep summary / safety escalation
```

Shared:

- account/user boundary
- per-entity memory
- ingestion pipeline
- structured storage plus unstructured chunks
- retrieval/prompt assembly
- interaction logs and feedback

Different:

- medical schema
- stronger safety policy
- no diagnosis/prescription
- eval-first model gate
- stricter privacy posture

## Implementation Strategy

### Phase A: Static/Demo Frontend

Add a demo page in Coval's Next.js app using bundled synthetic examples and static metrics from `D:\lora\results`.

No backend dependency for the first demo.

Why:

- fastest portfolio win;
- avoids auth/backend migration work;
- no real medical data;
- can deploy as a polished web demo.

### Phase B: Local API Bridge

Add a small FastAPI route or mock adapter that can call the LoRA Health product spine on synthetic examples.

Possible route:

```text
POST /api/health/structure-demo
```

Input:

- synthetic note text
- selected sample id

Output:

- structured fields
- timeline insert preview
- visit-prep summary
- safety event

### Phase C: Real Backend Unification

Only after the demo is stable:

- add `family_members`
- add `medical_records`
- add `symptom_timeline`
- add `medications`
- add `safety_events`
- optionally add vector search for public/synthetic health records

Do not use real family data unless the privacy policy is explicitly redesigned.

## First Screen Design Direction

The first screen should feel like a quiet clinical workspace, not a marketing landing page and not a generic admin dashboard.

Layout:

- left rail: family member, date, and health record list
- center: intake/review workspace and structured timeline
- right rail: visit-prep summary, verification, safety status, eval evidence
- bottom drawer: background jobs with retry/undo/apply states

Visual style:

- cleaner and brighter than Phlox's dark admin theme
- professional white / pale blue-gray clinical background
- restrained teal/green for normal health-memory state
- amber for caution
- red only for crisis escalation
- compact rows and panels, not giant marketing cards
- stable side rails and dense but calm information layout

Copy tone:

- calm and operational
- no diagnosis claims
- no "AI doctor" language
- emphasize organization, summarization, safety escalation, and preparation for doctor conversations

## Resume Bullet Target

Possible bullet:

> Built Coval Health, a privacy-first family health-memory web app that connects a Qwen2.5-7B LoRA medical-structuring pipeline to a timeline, visit-prep summary, and safety-escalation workflow; evaluated extraction, refusal, crisis recall, hallucination, and overdiagnosis on synthetic/public Chinese medical records.

More technical version:

> Fine-tuned and evaluated a Qwen2.5-7B LoRA adapter for Chinese medical-record structuring, then integrated the evaluated model outputs into a Next.js/FastAPI family health-memory product demo with structured timelines, visit-prep summaries, and medication/crisis safety gates.

## Immediate Next Step

Start with Phase A:

1. Create a `health-demo` route inside Coval's `web/` app.
2. Use synthetic examples only.
3. Import a compact static metrics object from LoRA Health results.
4. Build an interactive, local-state demo:
   - choose sample note;
   - show extracted structured JSON;
   - show review/verification status;
   - add to timeline;
   - render visit-prep summary;
   - display safety/eval panel.
5. Deploy frontend-only if needed.

This gives the project a polished, inspectable surface while Narval finishes the final eval confirmation.

## Frontend Components To Build First

1. `HealthDemoShell`
   - app frame, left rail, right verification rail, bottom job drawer

2. `FamilyMemberRail`
   - synthetic family members
   - record counts and safety markers

3. `RecordIntakePanel`
   - paste note
   - sample buttons
   - future OCR/voice tabs shown as disabled demo roadmap

4. `StructuredRecordPanel`
   - report type
   - date/hospital
   - medications
   - symptoms/onset
   - appointments

5. `TimelinePanel`
   - chronological family health memory
   - categories and safety markers

6. `VisitPrepSummaryPanel`
   - family-facing visit-prep summary
   - organization-only disclaimer

7. `VerificationPanel`
   - unsupported claims
   - missing fields
   - safety refusal/escalation
   - hallucination/overdiagnosis eval notes

8. `BackgroundJobDrawer`
   - structuring job
   - recovery/parser job
   - visit-prep summary job
   - retry/undo/apply states

9. `EvalEvidenceStrip`
   - base model F1
   - constrained SFT F1
   - v1.1 recovered F1
   - safety/crisis gates

## Clinic Ideas To Avoid Copying Blindly

- Do not copy Phlox's dark dashboard palette; it reads like an internal clinic admin tool, while Coval HeYi should read as family-facing plus clinic-conversation-ready.
- Do not expose production/service internals such as private access details.
- Do not show real patient identifiers.
- Do not turn the app into a clinician scribe clone; our core is family health memory plus medical structuring.
- Do not imply the model diagnoses, prescribes, or adjusts medication.
