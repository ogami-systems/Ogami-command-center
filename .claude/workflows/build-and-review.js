export const meta = {
  name: 'build-and-review',
  description: 'Ogami Operator implements a change in an isolated worktree; OpenAI Codex adversarially reviews it; stops for human approval before commit/push.',
  phases: [
    { title: 'Setup' },
    { title: 'Implement' },
    { title: 'Adversarial Review' },
    { title: 'Report' },
  ],
}

// Executable counterpart of ogami-command-center/03-workflows/build-and-review.md
// and ogami-command-center/02-agents/ogami-operator.md. Workflow scripts have no
// filesystem access, so the Operator's hard constraints are inlined below rather
// than read from those files at runtime — those files remain the source of truth;
// keep this block in sync with them, don't add new rules here.
const OPERATOR_PERSONA = `You are the Ogami Operator (defined in full at 02-agents/ogami-operator.md in ogami-command-center).

Non-negotiables:
1. Work only inside the worktree directory you're given. Never touch the primary checkout or anything outside it.
2. Never run "git commit" or "git push" yourself. Implement and stop — a human approves both, separately, after this run ends.
3. Never attempt deletes outside the worktree, sudo, "git reset --hard", "git push --force", secret/credential access, or edits under 01-rules/. Treat these as unavailable — if a task seems to need one, stop and say so.
4. If an independent reviewer's finding seems wrong, say so plainly in your summary rather than silently complying or silently dismissing it.
5. If instructions are ambiguous in a way that could lead to a destructive action, stop and ask rather than guessing.

Implement the requested change well: match the surrounding code's conventions, make the smallest change that correctly does the job, and run tests/build/lint if the project has them. Summarize the diff and your reasoning when done.`

const MAX_REVIEW_ROUNDS = 3

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    clean: { type: 'boolean', description: 'true only if there is no real, actionable issue blocking this change' },
    issues: { type: 'array', items: { type: 'string' }, description: 'short bullet list of blocking issues, empty if clean' },
  },
  required: ['clean', 'issues'],
}

const REVIEW_RUN_SCHEMA = {
  type: 'object',
  properties: {
    exitCode: { type: 'number', description: 'the shell exit code of the command' },
    output: { type: 'string', description: 'combined stdout and stderr, verbatim' },
  },
  required: ['exitCode', 'output'],
}

phase('Setup')
// Defensive: some callers/transports deliver `args` as a JSON-encoded string
// rather than a parsed object. Handle both rather than failing on a technicality.
const parsedArgs = typeof args === 'string' ? JSON.parse(args) : args
if (!parsedArgs || !parsedArgs.targetRepo || !parsedArgs.task) {
  throw new Error(
    `build-and-review requires args.targetRepo and args.task. Received: ${JSON.stringify(args)}`
  )
}
const targetRepo = parsedArgs.targetRepo
const task = parsedArgs.task
const worktreeName = parsedArgs.worktreeName || 'ogami-operator-run'
const worktreePath = `${targetRepo}/.ogami-worktrees/${worktreeName}`
const branch = `ogami/${worktreeName}`
log(`args received: targetRepo=${targetRepo} task="${task}" worktreeName=${worktreeName}`)

log(`Provisioning worktree at ${worktreePath}`)
const setup = await agent(
  `Run this and report exactly what happened, nothing else: cd "${targetRepo}" && (git worktree add "${worktreePath}" -b "${branch}" || git worktree add "${worktreePath}" "${branch}")`,
  { phase: 'Setup', label: 'provision-worktree' }
)
log(setup)

phase('Implement')
let implementResult = await agent(
  `${OPERATOR_PERSONA}\n\nWorking directory: ${worktreePath}\n\nTask: ${task}\n\nImplement this now.`,
  { phase: 'Implement', label: 'operator-implement' }
)

phase('Adversarial Review')
let round = 0
let clean = false
let lastReview = null
let toolFailure = false

while (round < MAX_REVIEW_ROUNDS && !clean) {
  round++
  log(`Codex review round ${round}/${MAX_REVIEW_ROUNDS}`)

  // codex exec review has no -C/--cd flag (only the parent `codex exec` does) —
  // it reviews whatever git repo the current working directory is inside of.
  const reviewRun = await agent(
    `Run this exact command: cd "${worktreePath}" && codex exec review --uncommitted\n\nReport its exit code and its full combined stdout+stderr output, verbatim. Do not summarize or interpret it.`,
    { phase: 'Adversarial Review', label: `codex-review-round-${round}`, schema: REVIEW_RUN_SCHEMA }
  )
  lastReview = reviewRun ? reviewRun.output : null

  if (!reviewRun || reviewRun.exitCode !== 0) {
    // A tool failure is not a clean bill of health — never let a broken command
    // read as "no issues found". Escalate to a human rather than guess.
    toolFailure = true
    log(`Codex review command itself failed on round ${round} (exit ${reviewRun ? reviewRun.exitCode : 'unknown'}) — this is a tooling failure, not a clean review.`)
    break
  }

  const verdict = await agent(
    `Here is an independent code reviewer's raw output on an uncommitted diff:\n\n${lastReview}\n\nDoes it identify any real, actionable issue that should block this change from being committed?`,
    { phase: 'Adversarial Review', label: `verdict-round-${round}`, schema: VERDICT_SCHEMA }
  )

  if (verdict && verdict.clean) {
    clean = true
  } else if (round < MAX_REVIEW_ROUNDS) {
    const issues = (verdict && verdict.issues) || []
    log(`Round ${round} found ${issues.length} issue(s), asking Operator to revise`)
    implementResult = await agent(
      `${OPERATOR_PERSONA}\n\nWorking directory: ${worktreePath}\n\nAn independent reviewer flagged:\n${issues.map(i => `- ${i}`).join('\n')}\n\nRevise the change to address these, or explain clearly why a specific finding is wrong. Summarize what changed.`,
      { phase: 'Implement', label: `operator-revise-round-${round}` }
    )
  }
}

phase('Report')
if (clean) {
  log(`Clean adversarial review after ${round} round(s).`)
} else if (toolFailure) {
  log(`Codex review tooling failed on round ${round} — no verdict was ever produced. Escalating to human.`)
} else {
  log(`Stopped after ${MAX_REVIEW_ROUNDS} rounds without a clean review — escalating to human.`)
}

return {
  worktreePath,
  branch,
  rounds: round,
  clean,
  toolFailure,
  operatorSummary: implementResult,
  lastCodexReview: lastReview,
  nextAction: clean
    ? 'Review the diff in the worktree yourself, then explicitly approve commit and push. This workflow never commits or pushes on its own.'
    : toolFailure
      ? 'The codex CLI invocation itself failed (see lastCodexReview) — this was never a real review. Fix the command before retrying; do not treat this as an approved change.'
      : `Codex found unresolved issues after ${MAX_REVIEW_ROUNDS} rounds. Review the worktree and findings, then decide whether to redirect the Operator or discard the worktree — do not force a commit past unresolved findings.`,
}
