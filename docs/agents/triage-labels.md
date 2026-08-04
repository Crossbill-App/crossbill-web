# Triage Labels

The five canonical triage roles use their default label strings — no mapping
needed: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`,
`wontfix`.

Of these, only `wontfix` currently exists on
`Crossbill-App/crossbill-web`; create the others on first use with
`gh label create`. They sit alongside the repo's existing topic labels (`bug`,
`enhancement`, `Tech debt`, `Frontend`, `backend`, `Nice to have`,
`ai-generated`, …), which are orthogonal to triage state.
