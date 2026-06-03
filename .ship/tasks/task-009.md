# Task 009: Scheduler jobs for the affiliate track

## Description
Wire validation and page-generation into the always-on scheduler, gated on Digistore24 readiness.

## Files
- `src/scheduler.py` (modify)

## Requirements
1. Add `affiliate_validate_job` wrapped in `_safe`: if `config.has_digistore()` is False, log idle + return; else `affiliate_research.validate_and_enrich()`. Interval ~8h.
2. Add `affiliate_pagegen_job` wrapped in `_safe`: gated on `has_digistore()`; call `affiliate_generate.generate_pending(limit=N)` (small N, e.g. 3, to respect LLM budget). Daily.
3. Register both in `create_scheduler()` with ids/names and misfire grace, matching existing jobs. Use deferred imports inside the job bodies (like `launch_job` imports `launch`) to avoid import-time side effects.
4. Update the summary log line to mention the two new jobs.

## Existing Code to Reference
- `src/scheduler.py` (`_safe`, `_engine_ready`, `add_job`, deferred import in `launch_job`)

## Acceptance Criteria
- [ ] Both jobs registered; scheduler builds without error
- [ ] Jobs idle cleanly (logged) when no Digistore24 key is set
- [ ] No import-time crash if LLM/key absent

## Dependencies
- Task 004, 006

## Commit Message
feat: scheduler jobs for affiliate validation and page generation
