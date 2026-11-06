# Git-history secret scan: no credential in any commit, ref or GitHub conversation, 2026-11-06

**Type: assessment. Not normative.** This records the result of action item AI-3 in
[the modernization and value assessment](syvrona-modernization-and-value-assessment-2026-11-05.md).
It changes nothing in the code and decides nothing about publication. It names files and
commits but contains no secret value.

Verified against source: `Termondt-Tech/syvrona-ai` `master` @ `a685431`, in the local
clone and in a fresh mirror of GitHub taken 2026-11-06. Scanner: gitleaks `v8.28.0`,
`ghcr.io/gitleaks/gitleaks@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854`.

---

## 0. Verdict

- **No real credential has ever been committed.** Every commit on every branch, tag and
  pull-request ref was scanned, plus every issue, pull request, comment and release on
  GitHub. There are zero true positives.
- **All 24 gitleaks hits are one false positive.** A fixture password literal in the
  sign-up tests in `tests/test_app.py` trips the `generic-api-key` rule. It is a form
  value for a local test database, not a credential for any system (§2).
- **The credential files were never committed.** `.env`, `.env.prod`, `.flaskenv`,
  `.flaskenv.prod`, `app/.flaskenv.dev` and `app.log` appear in no commit on any ref.
  `.gitignore` kept them out for the whole life of the repository.
- **Secrets no longer constrain the publication route.** The assessment's §7 allows a
  one-way export or an in-place flip after a scan. The scan is clean, so an in-place
  flip needs no history rewrite. Choose between the two routes on other grounds, chiefly
  the author email in §3.
- **AI-1 is unaffected.** The live keys still sit in the working tree and in every image
  built before 2026-11-06. Rotation remains P0.

## 1. Scope and method

| Surface | Size | Method | Result |
|---|---|---|---|
| Local clone, all refs | 165 commits (152 non-merge, 13 merge); 7 branches, 8 tags, 0 stashes, 0 unreachable commits | gitleaks `git` with `--log-opts="--all"`, then again with `--all -m` to include merge diffs | 8 findings, one class |
| GitHub mirror (`git clone --mirror`) | The same 165 commits. Adds 13 `refs/pull/*` refs; 0 commits exist on GitHub but not locally, and 0 the other way | gitleaks `git --all` | 8 findings, fingerprints identical to local |
| Next-commit tree | 208 files: tracked plus untracked-not-ignored, including the 2026-11-05 and 2026-11-06 documents | gitleaks `dir` | 8 findings, same class |
| GitHub metadata | 114 issues with 2 comments; 13 pull requests with 0 comments and 4 review comments; 7 releases with 0 assets; 0 discussions | `gh` export to JSON, then gitleaks `dir` | 0 findings |
| Key-shape search, all history | `git log --all -p -m`, 12 patterns: OpenAI and Anthropic `sk-`, Stripe `sk_live_` `sk_test_` `rk_live_` `whsec_`, Google `AIza`, Mailgun `key-`, MySQL and Redis URLs with passwords, GitHub tokens, PEM private keys | `grep -E -c` | 0 hits on every pattern, in history and in GitHub metadata |
| Credential files | The six files above, plus any `*.env*`, `*flaskenv*`, `*.log`, `*.sqlite`, `*.db`, `*.pem`, `*.key`, `*.p12`, `*.pfx` | `git log --all --diff-filter=A --name-only` | Never added on any ref |
| Binary blind spot | Four early versions of `requirements.txt` are UTF-16LE, so gitleaks skips them as binary | Decoded and checked line by line | Package pins only; no URL, index or token |

gitleaks reports 150 commits scanned without `-m` and 163 with it. The gap to 165 is
merge commits (without `-m`) and commits whose only change is binary. Every surface
was scanned with `--redact`, so no secret value reached a report or a terminal.

Reproduce from the repository root:

```bash
OUT=$(mktemp -d)
docker run --rm -v "$PWD":/repo:ro -v "$OUT":/out \
  ghcr.io/gitleaks/gitleaks@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854 \
  git /repo --log-opts="--all -m" --redact --no-banner --exit-code 0 \
  --report-format json --report-path /out/history.json
jq -r '.[] | [.RuleID, .File, .Commit[0:7]] | @tsv' "$OUT/history.json"
```

## 2. Findings

| ID | Rule | Location | Introduced | Classification |
|---|---|---|---|---|
| F1 | `generic-api-key` | `tests/test_app.py::test_register_new_user`, `::test_signup_missing_fields`, `::test_signup_duplicate_email`: the `password` and `confirm_password` form fields | `0ba7bf8` (2025-06-03), `9cbaa02` (2025-06-06), `63b1f29` (2025-07-01) | **False positive.** One fixture literal posted to the sign-up form against the SQLite test database. It authenticates nothing outside the test run. |

The same eight lines produce the eight hits in each of the three code surfaces. The
fingerprints are in §8 for a future `.gitleaksignore`.

## 3. What an in-place flip would still expose

None of these is a secret. Each is a publication choice for Rich.

- **Author email on every commit.** All 165 commits are authored as Rich Termondt with a
  personal `@gmail.com` address (316 author and committer fields). The other 14 fields
  are GitHub's `noreply` address from web edits and merges. An in-place flip publishes the
  personal address. A one-way export, or `git filter-repo --mailmap` on an export copy,
  replaces it.
- **Addresses in content.** `@termondttech.com` (26 occurrences) and `@syvrona.com` (3) in
  templates and docs. The rest are `example.com` or placeholders.
- **The backlog.** 114 issues, of which 48 are open per the assessment, and 13 pull
  requests with their review comments. All scanned clean.
- **No infrastructure detail.** No IPv4 address other than loopback appears anywhere in
  history. `deploy.sh` uses paths only, and the droplet guides use placeholders.
- **Actions.** 28 workflow runs, the newest 2025-12-19. Their logs have expired (`410 Gone`)
  and there are no artifacts. No workflow pushes an image to any registry.
- **Forks.** None.

## 4. Repository settings observed

- GitHub secret scanning is **disabled** on the repository; the alerts endpoint returns
  that message. It becomes free on a public repository.
- Visibility is private. Wiki and Pages are off. Discussions are enabled but empty.

## 5. Consequences for the assessment

- **AI-3 is done.** The history and the GitHub record are clean as of `a685431`.
- **§7's routes both stay open.** The deciding factor is now the commit email (§3), not
  secrets.
- **The scan is point-in-time.** Commits after `a685431`, including the pending commit of
  the 2026-11-05 and 2026-11-06 work, need a rescan before any flip. The next-commit tree
  was scanned clean today.

## 6. Action items

| ID | Priority | Urgency | Item | Owner |
|---|---|---|---|---|
| **SC-1** | **P0** | **[now]** | AI-1 is still open: rotate every credential in `.flaskenv`, `.flaskenv.prod`, `app/.flaskenv.dev`, `.env` and `.env.prod`, then delete the three `.flaskenv*` files and `app.log`. | Rich |
| **SC-2** | **P2** | **[before publish]** | Decide whether the personal email on 165 commits may be public. If not, publish by one-way export or rewrite the author map on an export copy. | Rich decides |
| **SC-3** | **P2** | **[before publish]** | Add a `.gitleaksignore` with the eight fingerprints in §8, and a gitleaks job in CI pinned by digest, so the known false positive cannot mask a real one. | agent |
| **SC-4** | **P2** | **[after flip]** | Enable secret scanning and push protection. | Rich |
| **SC-5** | **P3** | **[before publish]** | Re-run §1 against the final tip immediately before the flip or export. | agent |

## 7. Recommended end-state

1. Keys rotated and the local credential files deleted (SC-1).
2. A gitleaks job green in CI with the fixture allowlisted (SC-3).
3. The email decision made and the route chosen (SC-2).
4. A final rescan on the tip that goes public, then secret scanning on (SC-5, SC-4).

## 8. Appendix: fingerprints for `.gitleaksignore`

```
0ba7bf8d675b9768702076c14ad29d8a66f592e2:tests/test_app.py:generic-api-key:46
9cbaa026ace4172b5a697752638a4d7857987f14:tests/test_app.py:generic-api-key:48
63b1f29abd578faf2a06576ddc23f9fcf18546f6:tests/test_app.py:generic-api-key:99
63b1f29abd578faf2a06576ddc23f9fcf18546f6:tests/test_app.py:generic-api-key:101
63b1f29abd578faf2a06576ddc23f9fcf18546f6:tests/test_app.py:generic-api-key:139
63b1f29abd578faf2a06576ddc23f9fcf18546f6:tests/test_app.py:generic-api-key:141
63b1f29abd578faf2a06576ddc23f9fcf18546f6:tests/test_app.py:generic-api-key:151
63b1f29abd578faf2a06576ddc23f9fcf18546f6:tests/test_app.py:generic-api-key:153
```

A `dir` scan of the working tree fingerprints by `file:rule:line` instead. An inline
`# gitleaks:allow` on the eight current lines covers that case.

## 9. What this could not verify

> **Unverified:** whether any image built before 2026-11-06 was ever pushed to a registry.
> No workflow or script in the repository pushes one. Docker Hub, DigitalOcean Container
> Registry and GHCR accounts were not checked.

> **Unverified:** the contents of expired Actions logs. GitHub masks registered secrets in
> logs, and the workflows read none, but the logs themselves are gone.

> **Unverified:** coverage beyond gitleaks' default rules and the 12 shapes in §1. A secret
> with no keyword, no known prefix and low entropy would pass both.

> **Unverified:** whether the keys in the working-tree files are still live. They were not
> read and not tested. AI-1 treats them as live.

> **Unverified:** copies outside GitHub: the retired droplet's disk and backups, other
> clones, and gists.
