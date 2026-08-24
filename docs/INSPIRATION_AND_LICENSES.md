# External Inspiration and License Boundaries

Reviewed for Phase 0/1 on 2026-08-19. No upstream source file, UI asset, or
substantial code pattern was copied into Coval Health in this phase. The local
implementation was written independently with Python `sqlite3`, FastAPI, Next.js,
and Playwright.

| Project | Pattern studied | License boundary / decision |
| --- | --- | --- |
| [Korean CSAT LLM](https://github.com/jagaldol/korean-csat-llm) | Experiment tables, ablations, negative-result reporting, failure-driven data changes | No clear repository license was identified; no code or assets copied. |
| [体調Do？](https://qiita.com/rikum0730/items/73f1a49a2e053bd17daa) | Narrow check-in -> longitudinal summary -> clinician communication loop | Article inspiration only; no reusable source/license supplied and no code copied. |
| [MKTY-System](https://github.com/duyu09/MKTY-System) | Separate product/model services and visible ingestion status | MPL-2.0 plus extra attribution requirements; no source copied and diagnosis/multi-agent-opinion claims not adopted. |
| [OwnChart](https://github.com/nickpdawson/OwnChart) | Immutable raw sources, review candidates, provenance, user-canonical facts | PolyForm Noncommercial is not an ordinary open-source license; concepts independently reimplemented, no source/assets copied. |
| [PrivateScribe](https://github.com/secondpathstudio/privatescribe) | Draft/final workflow, append-only addenda, local privacy and audit posture | MIT project; no file-level reuse in this phase, so no attribution notice is required yet. |
| [Phlox](https://github.com/bloodworks-io/phlox) | Local FastAPI/Tauri/SQLCipher/llama.cpp packaging and explicit experimental warning | MIT project; packaging is deferred and no code copied. No clinic/private data was accessed. |
| [HealthSamurai PHR](https://github.com/HealthSamurai/phr) | Family context, migrations, seeded demo data, future FHIR mapping | Repository code is MIT, while Aidbox has separate licensing/activation; neither code nor backend dependency was adopted. |

If future work reuses an upstream file or substantial implementation pattern, add
`THIRD_PARTY_NOTICES.md` before merging. Record the upstream repository/path,
commit, license, local modifications, and tests.
