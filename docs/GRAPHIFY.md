# Graphify Workflow

Use graphify to reduce context load after the repo has enough code/docs to map.

## What To Graph

Start with this repo only:

```powershell
cd D:\lora
graphify . --wiki
```

Do not graph `data/private/`, `.env`, checkpoints, or generated outputs. They are ignored by `.gitignore`, but still think before running tools over local folders.

## Expected Outputs

Graphify writes to `graphify-out/`, which is ignored by Git:

- `graph.html` - interactive graph.
- `GRAPH_REPORT.md` - high-level report.
- `graph.json` - GraphRAG-ready graph data.
- optional `wiki/` export if `--wiki` is used.

## When To Use

- After Phase 1, to map eval files and metric modules.
- After Phase 3, to trace the product spine from ingest to safety output.
- Before a large refactor, to ask architecture questions without loading the whole repo.

## Query Pattern

Once `graphify-out/graph.json` exists:

```powershell
graphify query "How does the health record flow from OCR to doctor summary?"
graphify query "Which files implement safety escalation?"
```

Keep graphify outputs local unless the user explicitly asks to publish them.
