# 90-second interview demo

0-10s — Open the workbench and `/health`. Say: “This release accepts only
synthetic/public-safe data; real-data mode is code-gated.” Show schema/provider.

10-25s — Type an arbitrary Chinese synthetic note. Submit it. Explain that the
source is committed before the provider call and has a SHA-256 provenance link.

25-40s — Edit one extracted fact and the doctor-facing summary. Explain that this
is a candidate; it cannot enter timeline until approval, and safety is not editable.

40-58s — Approve, edit again, then undo. Show versions: undo appends a new head
instead of deleting history. Reload the page and show the record remains.

58-72s — Open the already-green recovery/vault test receipt rather than changing
providers live. Explain: source survives failure, retry gets a lease, reject
invalidates late output, and restore refuses to overwrite an existing database.

72-90s — Open the claim ledger/eval report. Say: “I connected the LoRA, but the
gate rejected promotion when crisis/refusal/comparator evidence was inadequate.
The product still works through review and deterministic safety.”

Useful commands are in the README. The full failure, restart, backup and browser
suite is a reproducible release gate, not a claim that every path fits into the
90-second live walkthrough. Never demo with real family data.
