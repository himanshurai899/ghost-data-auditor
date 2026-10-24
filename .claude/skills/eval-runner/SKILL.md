---
name: eval-runner
description: Runs the pipeline on the 32 public sample cases and custom cases, scores against sample_output.csv (status, step-level, field-level and sequence accuracy), compares with the last baseline, and updates code/evaluation/evaluation_report.md. Use after any change to code/ghost/, before merging, and at every phase exit (dev gate DG4).
---

Read and follow `.agents/skills/eval-runner/SKILL.md` (and the files it links) exactly. That is the canonical, tool-agnostic skill; this file is only a pointer.
