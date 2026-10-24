# Enhanced Task Spec — template

Copy this block, fill every tag, and delete the hint text. Keep it under about 60 lines; link to files instead of pasting them.

```xml
<task_spec id="TS-<yyyymmdd>-<nn>" backlog="<P#-##[, P#-##]> | NEW: <proposed title>" owner="<coordinator|data-analyst|implementer|evaluator|security-guardian>">

<original_ask lang="<iso-639-1>">
<verbatim user text; translation below if not English>
</original_ask>

<role>
You are the <owner> agent on the Ghost Data deletion-audit project. <One sentence of expertise relevant to this task.>
</role>

<context>
- Phase: <P#> (from .agents/memory/progress.md)
- Relevant files: <path:line …>
- Relevant facts: <bullets from dataset_facts.md / decisions.md, with ids>
- Current metric / state: <e.g. sample sequence accuracy 62% (gate_log row N)>
</context>

<goal>
<The outcome the author wants, 1–2 sentences. Name the target it moves: scoring dimension | gate | demo moment | deliverable.>
</goal>

<task>
1. <imperative, concrete step>
2. <…>
</task>

<scope>
In: <files/modules>
Out (non-goals): <explicitly excluded work>
</scope>

<constraints>
- <standing constraints from SKILL.md>
- <task-specific constraints>
</constraints>

<assumptions>
- <default chosen for an ambiguity, and why>
</assumptions>

<acceptance_criteria>
- [ ] <observable result #1 — command + expected output or artifact>
- [ ] <…>
</acceptance_criteria>

<verification>
<exact commands, e.g. `python code/main.py --cases case_05` then `python scripts/gate.py contract`>
</verification>

<output_format>
<what the executor returns: diff summary, metrics table, file list>
</output_format>

<open_questions>
- <only if blocking; else "none">
</open_questions>

<rubric grounded="2" intent="2" scoped="2" testable="2" safe="2" sized="2" unambiguous="2" total="14"/>
</task_spec>
```
