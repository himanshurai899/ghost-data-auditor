# Prompt Enhancer — worked examples

## Example 1 — vague accuracy ask

**Raw ask:** "output is wrong for some cases, fix it"

```xml
<task_spec id="TS-20261025-03" backlog="P2-09" owner="evaluator">
<original_ask lang="en">output is wrong for some cases, fix it</original_ask>
<role>You are the evaluator agent. You triage scorer diffs into root causes before anyone edits logic.</role>
<context>
- Phase: P2
- Files: code/evaluation/main.py, code/ghost/planner.py, code/ghost/reasoning.py
- Last scorer run: status 91%, sequence 64% (audit/gate_log.md latest eval row)
</context>
<goal>Raise sample sequence accuracy without regressing status accuracy. Target: DG4 eval gate + "step order" scoring dimension.</goal>
<task>
1. Run the scorer and group failing sample cases by first differing field (status / missing step / extra step / order / evidence_id).
2. For the largest group, find the root cause in one function and hand a fix spec to the implementer.
3. Record the failure and fix in evaluation_report.md "Failures and improvements".
</task>
<scope>In: scorer output, one root cause. Out: new features, LLM prompt changes.</scope>
<constraints>
- Only code/evaluation reads sample_output.csv; never hardcode sample answers.
- Deterministic; no secrets; masked identifiers in the report.
</constraints>
<assumptions>- "Wrong" means mismatches vs sample_output.csv, since the hidden set isn't available.</assumptions>
<acceptance_criteria>
- [ ] `python code/evaluation/main.py` shows sequence accuracy above 64%, and status accuracy at least 91%
- [ ] evaluation_report.md has a new failure/fix entry
</acceptance_criteria>
<verification>`python scripts/gate.py eval`</verification>
<output_format>Before/after metric table + root-cause sentence + files changed.</output_format>
<open_questions>none</open_questions>
<rubric grounded="2" intent="2" scoped="2" testable="2" safe="2" sized="2" unambiguous="2" total="14"/>
</task_spec>
```

## Example 2 — non-English, wow-oriented ask

**Raw ask:** "demo mein kuch wow chahiye jab case incomplete ho"

```xml
<task_spec id="TS-20261025-07" backlog="P3-04" owner="implementer">
<original_ask lang="hi">demo mein kuch wow chahiye jab case incomplete ho
(translation: "I want something wow in the demo when a case is incomplete")</original_ask>
<role>You are the implementer agent building the React operator console.</role>
<context>
- Phase: P3; API in code/ghost/api.py; UI in web/src/
- Demo script step 4 (docs/delivery_plan.md §5) = resurrection timeline
</context>
<goal>When an INCOMPLETE case opens, show visually *why*: deleted → recreated by sync → still present at audit_at. Target: demo moment P3-04.</goal>
<task>
1. Add GET /api/cases/{id}/timeline that returns facts ordered by observed_at, with masked subject keys.
2. Render a horizontal timeline with an audit_at marker; evidence chips open the source snippet.
</task>
<scope>In: api.py timeline route, web/src timeline component. Out: identity graph, chat.</scope>
<constraints>
- No raw PII in API responses (safety.mask); regex-validated case id; no dangerouslySetInnerHTML.
</constraints>
<assumptions>- "Wow" = the resurrection timeline, the strongest single visual in the plan.</assumptions>
<acceptance_criteria>
- [ ] Opening a known INCOMPLETE sample case shows DELETE → SYNC → PRESENT in order
- [ ] `npm run build` passes; `python scripts/gate.py security` passes
</acceptance_criteria>
<verification>Run API + `npm run dev`; open the case; then run both gates.</verification>
<output_format>Screenshot path + files changed.</output_format>
<open_questions>none</open_questions>
<rubric grounded="2" intent="2" scoped="2" testable="2" safe="2" sized="2" unambiguous="2" total="14"/>
</task_spec>
```
