---
name: security-gate
description: Runs the security gate (DG5) for the Ghost Data project — secret scan, golden-label leakage scan, unsafe-API scan (eval/exec/pickle/shell=True/dangerouslySetInnerHTML), PII-in-log scan, .env tracking check — and reviews changes against the threat model T1–T17 in docs/architecture.md §7. Use before every commit or merge, before packaging, and whenever code touches parsing, the LLM client, the API, or the UI.
---

Read and follow `.agents/skills/security-gate/SKILL.md` (and the files it links) exactly. That is the canonical, tool-agnostic skill; this file is only a pointer.
