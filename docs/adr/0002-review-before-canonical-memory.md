# ADR 0002: Review before canonical memory

Status: accepted.

A model output is stored as a machine candidate, never directly as canonical
history. The user may edit it, but safety fields remain server-controlled.
Approval appends version 1; later edits and undo append new versions. Timeline
queries join only approved records/current versions.

This costs an extra user action and more schema, but it makes provenance,
correction, stale-write rejection and audit reconstruction explicit. The rejected
alternative—overwriting one JSON document—cannot explain who changed what or
prevent an old browser tab from erasing a newer correction.
