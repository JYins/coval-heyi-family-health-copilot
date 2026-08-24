# ADR 0004: Vault v1 proves recovery, not confidentiality

Status: accepted with explicit block.

Vault v1 uses SQLite online backup, resource-bounded ZIP parsing, SHA-256/size
checks, migration-ledger validation, clean-target install and a restore migration
drill. Its FHIR R4 document Bundle is a conservative mapping, not certified
conformance.

The manifest deliberately says `encryption: none` and `authenticity: unsigned`.
Hashes detect accidental corruption but are not a signature. This foundation is
useful for testing portability, while real data stays disabled until a mature
encrypted container, OS key custody and independent recovery drill exist.
