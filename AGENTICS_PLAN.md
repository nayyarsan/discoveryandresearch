# Agentics Plan — discoveryandresearch

Add [GitHub Agentic Workflows](https://github.com/githubnext/agentics) to the AI repo discovery engine.

## Prerequisites

```bash
gh extension install github/gh-aw
```

## Workflows to Add

- [ ] **Weekly Research** — augments the discovery engine's source set with arXiv + curated research papers
  ```bash
  gh aw add-wizard githubnext/agentics/weekly-research
  ```

- [ ] **Discussion Task Miner** — extracts actionable improvement tasks from discussions/issues automatically
  ```bash
  gh aw add-wizard githubnext/agentics/discussion-task-miner
  ```

- [ ] **Daily Repo Status** — creates activity reports on the discovery pipeline's own health
  ```bash
  gh aw add-wizard githubnext/agentics/daily-repo-status
  ```

- [ ] **Repository Quality Improver** — rotating quality review across code, docs, security, and testing
  ```bash
  gh aw add-wizard githubnext/agentics/repository-quality-improver
  ```

- [ ] **Duplicate Code Detector** — the scraping/filtering logic across 9 sources likely has repetition
  ```bash
  gh aw add-wizard githubnext/agentics/duplicate-code-detector
  ```

- [ ] **Daily Malicious Code Scan** — scans for supply-chain risks in scraping/HTTP deps
  ```bash
  gh aw add-wizard githubnext/agentics/daily-malicious-code-scan
  ```

- [ ] **Issue Triage** — auto-labels incoming issues and PRs
  ```bash
  gh aw add-wizard githubnext/agentics/issue-triage
  ```

- [ ] **Plan** (`/plan` command) — breaks big issues into tracked sub-tasks
  ```bash
  gh aw add-wizard githubnext/agentics/plan
  ```

## Keep Workflows Updated

```bash
gh aw upgrade
gh aw update
```
