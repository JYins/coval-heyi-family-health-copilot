# 90-second interview demo

0-10s — Open the workbench and `/health`. Say: “This release accepts only
synthetic/public-safe data; real-data mode is code-gated.” Show schema/provider.

10-25s — Type an arbitrary Chinese synthetic note. Submit it. Explain that the
source is committed before the provider call and has a SHA-256 provenance link.

25-40s — Edit one extracted fact and the doctor-facing summary. Explain that this
is a candidate; it cannot enter timeline until approval, and safety is not editable.

40-55s — Approve, edit again, then undo. Show versions: undo appends a new head
instead of deleting history. Reload or restart the API and show the record remains.

55-68s — Use a synthetic failing provider (or show its test) and the recovery
inbox: the source remains, retry gets a lease, and reject invalidates late output.

68-78s — Run vault backup -> verify -> restore into a clean path. Explicitly say
v1 is unencrypted/unsigned; the point demonstrated is recovery correctness.

78-90s — Open the claim ledger/eval report. Say: “I connected the LoRA, but the
gate rejected promotion when crisis/refusal/comparator evidence was inadequate.
The product still works through review and deterministic safety.”

Useful commands are in the README. Never demo with real family data.
