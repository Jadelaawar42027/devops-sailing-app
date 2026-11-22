# Definition of Done

Applied to every backlog item (brief §2). An item is **Done** only when all of these are true:

1. **Merged to `main` through a pull request reviewed and approved by another team member.**
   No direct pushes to `main` (branch protection is on).
2. **CI is green** on the pull request: lint, format check, tests with coverage at or above 70%,
   image build.
3. **Deployed**: the CD run for the merge commit finished green, so the change is live on Azure and
   `/health` plus the end-to-end smoke test passed against it.
4. The acceptance criteria of the user story are met and were checked on the deployed app.
5. New or changed behaviour has tests (unit or API level); bugs get a test that failed before the fix.
6. No secrets, keys or passwords in the code, the history, the images or the logs.
7. Docs updated where the change affects them (README, decisions, data model, monitoring).
8. AI-assisted work is logged in `AI_USAGE.md`, and the author can explain every line of it.
