# Coval HeYi Design QA

Status: passed after the 2026-07-01 `2+3` redesign pass.

## Current Direction

- Desktop: clinic-style review sheet with a dark navigation rail, compact record composer, structured review table, right-side safety / summary / completeness / automation / model evidence inspector, and a bottom timeline strip.
- Mobile: iOS-like record-first page. The first viewport opens directly on `新建记录`, patient switcher, save action, input mode tabs, note text, attachment action, and `智能整理`.
- Palette: restrained charcoal navigation, pale clinical workspace, deep green action color, amber/red only for safety states.
- Anti-AI cleanup: removed colorful dashboard sections, long evidence column, gradient/glass effects, decorative metric cards, and excessive pills.

## Rendered Evidence

- Desktop screenshot: `D:\lora\results\webapp\qa\coval-heyi-redesign-final-desktop.png`
- Mobile screenshot: `D:\lora\results\webapp\qa\coval-heyi-redesign-final-mobile.png`
- README assets:
  - `D:\lora\docs\assets\coval-heyi-desktop.png`
  - `D:\lora\docs\assets\coval-heyi-mobile.png`

## Checks

- Page identity: passed. `http://127.0.0.1:3000`, title `Coval HeYi`.
- Desktop one-screen fit: passed at 1440x1024. `scrollWidth=1440`, `scrollHeight=1024`, no horizontal or vertical overflow.
- Desktop structure: passed. The right-side `模型证据` table is compact and no longer stretches into a long column.
- Mobile first screen: passed at 390x844. The first visible workflow is record creation, not a dashboard or hidden sheet.
- Mobile overlap: passed after disabling mobile flex shrink on panels. `智能整理` no longer overlaps the structured review panel.
- Safety posture: passed. Visible copy says `仅整理信息，不替代诊断`.
- Interaction: passed. `智能整理` / `确认保存` still save the selected synthetic record into the timeline state.

## Verification Commands

- `npm.cmd run typecheck`
- `npm.cmd run lint`
- `npm.cmd run build`
- `powershell -ExecutionPolicy Bypass -File scripts\run_workflow_checks.ps1`

## Remaining Notes

- The UI is still a synthetic/public-data demo and does not diagnose, prescribe, or adjust medication.
- The frontend stack remains Next.js App Router + React + TypeScript, backed by the optional FastAPI evidence endpoint in `src/serve/coval_health_api.py`.
