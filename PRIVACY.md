# Privacy boundary

- The current app, textarea, API, SQLite database, FHIR export and vault accept
  **synthetic/public-safe data only**. Do not enter real names, reports, symptoms,
  medications or family/patient information anywhere in this build.
- Repository, CI, screenshots, model training and evaluation use only public or
  synthetic data.
- Real family data must not enter Git, Hugging Face, Narval, cloud services,
  logs, screenshots or tests.
- The current SQLite database and vault v1 are not encrypted at rest.
- `COVAL_REAL_DATA_MODE=1` fails closed until the gates in
  `docs/THREAT_MODEL.md` pass.
- The software organizes records and prepares clinician conversations; it does
  not diagnose, prescribe or adjust medication.

Delete local synthetic demo databases through normal filesystem controls. A
verified in-product purge for real data is not yet implemented.
