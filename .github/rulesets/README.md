# Branch rulesets (D-023)

Applied on 2026-10-25 with `gh api -X POST repos/OWNER/REPO/rulesets --input .github/rulesets/<file>.json`. These files are the record; GitHub holds the live copy (Settings > Rules).

| Ruleset | Branch | Enforces |
|---|---|---|
| `protect-main` | `main` | pull request required; 1 approval; **code-owner review** (`.github/CODEOWNERS`: the repository owner); stale approvals dismissed on push; approval of the last push required; conversations resolved; merge commits only; no force-push; no deletion. Repository admins may bypass only in pull-request mode (an explicit, visible action). |
| `protect-develop` | `develop` | pull request required (0 approvals so the Gitflow works); no force-push; no deletion. CODEOWNERS auto-requests the owner on every PR. |

Limits, stated plainly: GitHub does not allow an author to approve their own PR, so the owner merges their own PRs with the admin bypass; and all agent work is pushed under the owner's GitHub login, so GitHub cannot separate agent commits from the owner's by author. Agents therefore follow the rule in `.agents/agents/coordinator.md` (never self-approve, never `--admin`, never merge into `main` without the user's go-ahead). Feature and bugfix branches are not restricted (agents use `--force-with-lease` on their own branches).
