#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ship.sh - Spec-Driven Feature Development Orchestrator for Claude Code
#
# 5-phase workflow: requirements → planning → breakdown → implementation → testing
# Phase 4 spawns isolated sub-agents. Phase 5 writes Playwright tests + verifies.
#
# Usage: ./ship.sh <command> [args]
# Run ./ship.sh help for all commands.
# =============================================================================

# --- Configuration ---
SHIP_DIR=".ship"
STATE_FILE="$SHIP_DIR/state.json"
CONTEXT_FILE="$SHIP_DIR/context.md"
TASKS_DIR="$SHIP_DIR/tasks"
LOGS_DIR="$SHIP_DIR/logs"
BLOCKERS_DIR="$SHIP_DIR/blockers"
SPEC_FILE="$SHIP_DIR/spec.md"
PLAN_FILE="$SHIP_DIR/plan.md"
MASTER_TASKS="$SHIP_DIR/tasks.md"
LEARNINGS_FILE="$SHIP_DIR/learnings.md"

SHIP_MODEL="${SHIP_MODEL:-sonnet}"
SHIP_MAX_BUDGET="${SHIP_MAX_BUDGET:-2.00}"
SHIP_PLAYWRIGHT_CMD="${SHIP_PLAYWRIGHT_CMD:-npx playwright test}"
SHIP_CLAUDE_FLAGS="${SHIP_CLAUDE_FLAGS:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# --- Helpers ---

now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
pad() { printf '%03d' "$1"; }

die() {
  echo -e "${RED}Error: $1${NC}" >&2
  exit 1
}

check_deps() {
  command -v jq &>/dev/null || die "jq is required. Install: sudo apt install jq"
  command -v claude &>/dev/null || die "claude CLI not found. Install Claude Code first."
}

check_init() {
  [ -f "$STATE_FILE" ] || die "Not initialized. Run: ./ship.sh init"
}

get_state() {
  jq -r ".$1" "$STATE_FILE"
}

set_state() {
  local tmp
  tmp=$(mktemp)
  if [[ "$2" =~ ^-?[0-9]+$ ]]; then
    jq ".$1 = $2 | .updated_at = \"$(now)\"" "$STATE_FILE" > "$tmp"
  elif [[ "$2" == "["* || "$2" == "{"* || "$2" == "true" || "$2" == "false" ]]; then
    jq ".$1 = $2 | .updated_at = \"$(now)\"" "$STATE_FILE" > "$tmp"
  else
    jq ".$1 = \"$2\" | .updated_at = \"$(now)\"" "$STATE_FILE" > "$tmp"
  fi
  mv "$tmp" "$STATE_FILE"
}

array_push() {
  local tmp
  tmp=$(mktemp)
  jq ".$1 += [$2] | .updated_at = \"$(now)\"" "$STATE_FILE" > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

array_contains() {
  jq -e ".$1 | index($2)" "$STATE_FILE" &>/dev/null
}

# --- Commands ---

cmd_init() {
  local feature_name="${1:-}"

  echo -e "${CYAN}${BOLD}Initializing Ship${NC}"

  mkdir -p "$TASKS_DIR" "$LOGS_DIR" "$BLOCKERS_DIR"

  if [ -f "$STATE_FILE" ]; then
    echo -e "${YELLOW}State file already exists. Use './ship.sh reset' to start over.${NC}"
    cmd_status
    return 0
  fi

  if [ -z "$feature_name" ]; then
    echo -n "Feature name (short, e.g. 'user-profiles'): "
    read -r feature_name
    [ -z "$feature_name" ] && die "Feature name required"
  fi

  cat > "$STATE_FILE" << EOF
{
  "project": "ship",
  "feature": "$feature_name",
  "phase": "requirements",
  "current_task": 0,
  "total_tasks": 0,
  "completed_tasks": [],
  "skipped_tasks": [],
  "failed_tasks": [],
  "playwright_cmd": "$SHIP_PLAYWRIGHT_CMD",
  "tests_written": false,
  "verified": false,
  "created_at": "$(now)",
  "updated_at": "$(now)"
}
EOF

  cat > "$CONTEXT_FILE" << 'EOF'
# Ship Context Log

## Key Decisions
<!-- Important decisions from spec/planning phases -->

## Constraints
<!-- Technical or business constraints -->

## Notes
<!-- Important notes for sub-agents -->
EOF

  # Learnings persists across features — only create if missing
  if [ ! -f "$LEARNINGS_FILE" ]; then
    cat > "$LEARNINGS_FILE" << 'EOF'
# Project Learnings

> Non-obvious discoveries from implementation. Agents append findings here.

EOF
  fi

  cat > "$SHIP_DIR/.gitignore" << 'EOF'
logs/
blockers/
EOF

  echo ""
  echo -e "${GREEN}Initialized .ship/ for feature: ${BOLD}$feature_name${NC}"
  echo ""
  echo -e "Next steps:"
  echo -e "  ${BOLD}Option A:${NC} Run ${CYAN}./ship.sh spec${NC} to start requirements gathering"
  echo -e "  ${BOLD}Option B:${NC} Open Claude Code and type ${CYAN}/ship${NC}"
}

cmd_status() {
  check_init

  local phase current total completed skipped failed feature playwright_cmd tests_written verified
  phase=$(get_state "phase")
  current=$(get_state "current_task")
  total=$(get_state "total_tasks")
  completed=$(jq '.completed_tasks | length' "$STATE_FILE")
  skipped=$(jq '.skipped_tasks | length' "$STATE_FILE")
  failed=$(jq '.failed_tasks | length' "$STATE_FILE")
  feature=$(get_state "feature")
  playwright_cmd=$(get_state "playwright_cmd")
  tests_written=$(get_state "tests_written")
  verified=$(get_state "verified")

  echo ""
  echo -e "${BOLD}  Ship Status${NC}"
  echo -e "  Feature: ${CYAN}$feature${NC}"
  echo ""

  local phases=("requirements" "planning" "breakdown" "implementation" "testing" "complete")
  echo -n "  "
  for p in "${phases[@]}"; do
    if [ "$p" = "$phase" ]; then
      echo -ne "${GREEN}${BOLD}[$p]${NC} "
    else
      echo -ne "${DIM}$p${NC} "
    fi
    [ "$p" != "complete" ] && echo -ne "${DIM}→${NC} "
  done
  echo ""

  echo ""
  echo -e "  Model:   ${CYAN}$SHIP_MODEL${NC} | Budget: \$${SHIP_MAX_BUDGET}"
  echo -e "  Tests:   ${CYAN}$playwright_cmd${NC}"
  [ "$tests_written" = "true" ] && echo -e "  Written: ${GREEN}yes${NC}" || echo -e "  Written: ${DIM}no${NC}"
  [ "$verified" = "true" ]      && echo -e "  Verified: ${GREEN}yes${NC}" || echo -e "  Verified: ${DIM}no${NC}"

  if [ "$total" -gt 0 ]; then
    echo ""
    local pct=0
    [ "$total" -gt 0 ] && pct=$((completed * 100 / total))

    echo -e "  Tasks: ${BOLD}$completed${NC}/$total completed ($pct%)"
    [ "$phase" = "implementation" ] && echo -e "  Current: Task $current"
    [ "$skipped" -gt 0 ] && echo -e "  Skipped: ${YELLOW}$skipped${NC}"
    [ "$failed" -gt 0 ]  && echo -e "  Failed:  ${RED}$failed${NC}"

    local bar_w=30
    local filled=$((pct * bar_w / 100))
    local empty=$((bar_w - filled))
    echo -n "  ["
    [ "$filled" -gt 0 ] && printf "${GREEN}%0.s█${NC}" $(seq 1 "$filled")
    [ "$empty" -gt 0 ]  && printf "%0.s░" $(seq 1 "$empty")
    echo -e "] $pct%"
  fi

  echo ""
  echo -e "  ${BOLD}Files:${NC}"
  [ -f "$SPEC_FILE" ]      && echo -e "    ${GREEN}✓${NC} spec.md"      || echo -e "    ${DIM}○${NC} spec.md"
  [ -f "$PLAN_FILE" ]      && echo -e "    ${GREEN}✓${NC} plan.md"      || echo -e "    ${DIM}○${NC} plan.md"
  [ -f "$MASTER_TASKS" ]   && echo -e "    ${GREEN}✓${NC} tasks.md"     || echo -e "    ${DIM}○${NC} tasks.md"
  [ -f "$LEARNINGS_FILE" ] && echo -e "    ${GREEN}✓${NC} learnings.md" || echo -e "    ${DIM}○${NC} learnings.md"
  local task_count
  task_count=$(find "$TASKS_DIR" -name 'task-*.md' 2>/dev/null | wc -l || true)
  [ "$task_count" -gt 0 ] && echo -e "    ${GREEN}✓${NC} $task_count task files"

  local blocker_count
  blocker_count=$(find "$BLOCKERS_DIR" -name '*.md' 2>/dev/null | wc -l || true)
  if [ "$blocker_count" -gt 0 ]; then
    echo ""
    echo -e "  ${RED}Blockers ($blocker_count):${NC}"
    for f in "$BLOCKERS_DIR"/*.md; do
      echo -e "    - $(basename "$f")"
    done
  fi
  echo ""
}

cmd_spec() {
  check_init
  set_state "phase" "requirements"

  echo -e "${CYAN}Launching requirements gathering session...${NC}"
  echo ""

  claude \
    "I'm starting the Ship requirements gathering phase.

Read these files first:
1. .ship/state.json
2. .ship/context.md
3. .ship/learnings.md (if it exists — known project issues)
4. .ship/spec.md (if it exists — means we're revising)
5. .claude/CLAUDE.md or CLAUDE.md (project conventions)

Ask me structured questions about the feature I want to build, ONE CATEGORY AT A TIME:
1. Feature overview (what, why, for whom)
2. User stories and flows
3. Technical constraints and integrations
4. UI/UX requirements
5. Scope boundaries

After gathering all answers, create .ship/spec.md with:
- Feature Summary
- Problem Statement
- User Stories (with acceptance criteria per story)
- Technical Requirements
- UI/UX Requirements
- Integration Points
- Out of Scope
- Success Criteria

Ask me to review and approve it.
After approval, update .ship/state.json: set phase to 'planning'.
Log key decisions to .ship/context.md."
}

cmd_plan() {
  check_init
  [ -f "$SPEC_FILE" ] || die "spec.md not found. Run './ship.sh spec' first."
  set_state "phase" "planning"

  echo -e "${CYAN}Launching technical planning session...${NC}"
  echo ""

  claude \
    "I'm starting the Ship technical planning phase.

Read these files:
1. .ship/state.json
2. .ship/spec.md (approved feature spec)
3. .ship/context.md
4. .ship/learnings.md (known issues — apply relevant lessons)
5. .claude/CLAUDE.md or CLAUDE.md (project conventions and stack)

Create .ship/plan.md covering:
1. Architecture integration (how it fits the existing structure)
2. Database changes (if applicable)
3. API design (routes, auth requirements)
4. Frontend components (pages, components, UI patterns)
5. Service integrations (as needed)
6. Complete file map (every file to create or modify)

Read existing relevant files to understand current patterns before planning.
Present the plan section by section, checking for feedback.

After approval:
- Update .ship/state.json: set phase to 'breakdown'
- Log technical decisions to .ship/context.md."
}

cmd_breakdown() {
  check_init
  [ -f "$PLAN_FILE" ] || die "plan.md not found. Run './ship.sh plan' first."
  set_state "phase" "breakdown"

  echo -e "${CYAN}Launching task breakdown session...${NC}"
  echo ""

  claude \
    "I'm starting the Ship task breakdown phase.

Read these files:
1. .ship/state.json
2. .ship/spec.md
3. .ship/plan.md
4. .ship/context.md

Break the technical plan into small, sequential, independently-implementable tasks.

TASK SIZING: 15-45 min each, 1-5 files each, one clear purpose.

ORDERING: schema/migrations → API routes → components/pages → wiring → integrations → polish

For EACH task, create .ship/tasks/task-NNN.md:
\`\`\`
# Task NNN: [Title]

## Type
ui  ← include ONLY for tasks involving UI/UX (components, pages, forms, layouts, styling)
    ← omit this section entirely for backend, API, DB, config, or wiring tasks

## Description
[What to implement and why]

## Files
- \`path/to/file.ts\` (create|modify)

## Requirements
1. [Specific requirement]

## Existing Code to Reference
- \`path/to/existing.ts\` (pattern to follow)

## Acceptance Criteria
- [ ] [Criterion]

## Dependencies
- Task NNN (if any)

## Commit Message
type: description
\`\`\`

Also create .ship/tasks.md with a master checklist.

After creating all tasks, update .ship/state.json:
- phase = 'implementation'
- total_tasks = [count]
- current_task = 1

Show me the task list for review before finalizing.
Tell me to run './ship.sh run all' for automated execution."
}

# --- Implementation Phase ---

find_next_task() {
  local total
  total=$(get_state "total_tasks")
  [ "$total" -eq 0 ] && { echo "0"; return; }

  for i in $(seq 1 "$total"); do
    if ! array_contains "completed_tasks" "$i" && ! array_contains "skipped_tasks" "$i"; then
      echo "$i"
      return
    fi
  done
  echo "0"
}

run_single_task() {
  local task_num=$1
  local padded
  padded=$(pad "$task_num")
  local task_file="$TASKS_DIR/task-${padded}.md"

  [ -f "$task_file" ] || die "Task file not found: $task_file"

  if array_contains "completed_tasks" "$task_num"; then
    echo -e "${YELLOW}Task $task_num already completed.${NC}"
    return 0
  fi

  local total
  total=$(get_state "total_tasks")
  local task_title
  task_title=$(head -1 "$task_file" | sed 's/^# //')

  echo ""
  echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
  echo -e "  ${CYAN}Task $task_num / $total${NC}: $task_title"
  echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
  echo ""

  set_state "current_task" "$task_num"

  # Detect if this is a UI task
  local is_ui=false
  grep -qi "^## Type" "$task_file" && grep -qi "ui" "$task_file" && is_ui=true

  local system_prompt
  system_prompt=$(cat << 'SYSPROMPT'
You are a Ship sub-agent. Execute ONE task in isolation.

RULES:
1. Implement ONLY what the task specifies — nothing else
2. Follow existing codebase patterns and conventions
3. Create/modify ONLY the files listed in the task
4. Write clean, production-quality code — no placeholders or TODOs
5. Commit with EXACTLY the commit message from the task
6. Do NOT read other task files in .ship/tasks/
7. Do NOT modify any .ship/ files except learnings.md
8. If blocked, create .ship/blockers/task-NNN.md explaining why
9. If you discover something non-obvious about this codebase, append a brief note to .ship/learnings.md
SYSPROMPT
)

  # Build UI-specific design instructions if this is a UI task
  local ui_instructions=""
  if [ "$is_ui" = true ]; then
    ui_instructions=$(cat << 'UIPROMPT'

UI/UX TASK — Before writing any code, follow the design reference skill:
1. Read .claude/skills/design-ref/SKILL.md
2. Use Playwright to fetch a real component from https://21st.dev/community/components that matches this task
3. Extract its color palette, typography, and layout patterns
4. Apply those patterns + real Unsplash images (from the skill's photo ID table) to your implementation
5. Follow the anti-generic layout rules in the skill — no placeholder boxes, no Lorem ipsum, no 3-column card defaults
UIPROMPT
)
  fi

  local user_prompt
  user_prompt=$(cat << USERPROMPT
You are executing Task $task_num of $total.

Read in order:
1. .ship/tasks/task-${padded}.md (your task)
2. .ship/spec.md
3. .ship/plan.md
4. .ship/context.md

Then read any existing files referenced in the task.${ui_instructions}

Implement, commit. If blocked, create a blocker file.
USERPROMPT
)

  local log_file="$LOGS_DIR/task-${padded}.log"

  echo -e "  Model: ${SHIP_MODEL} | Budget: \$${SHIP_MAX_BUDGET}"
  echo -e "  Log:   $log_file"
  [ "$is_ui" = true ] && echo -e "  ${CYAN}UI task — design intelligence enabled${NC}"
  echo -e "${DIM}───────────────────────────────────────────────${NC}"

  local allowed_tools="Read,Write,Edit,Bash,Glob,Grep"
  if [ "$is_ui" = true ]; then
    allowed_tools="${allowed_tools},mcp__plugin_playwright_playwright__browser_navigate,mcp__plugin_playwright_playwright__browser_snapshot,mcp__plugin_playwright_playwright__browser_take_screenshot,mcp__plugin_playwright_playwright__browser_click,mcp__plugin_playwright_playwright__browser_wait_for"
  fi

  local exit_code=0
  claude -p "$user_prompt" \
    --append-system-prompt "$system_prompt" \
    --allowedTools "$allowed_tools" \
    --model "$SHIP_MODEL" \
    --max-budget-usd "$SHIP_MAX_BUDGET" \
    --permission-mode "bypassPermissions" \
    $SHIP_CLAUDE_FLAGS \
    2>&1 | tee "$log_file" || exit_code=$?

  echo -e "${DIM}───────────────────────────────────────────────${NC}"

  if [ "$exit_code" -eq 0 ]; then
    array_push "completed_tasks" "$task_num"

    if [ -f "$MASTER_TASKS" ]; then
      sed -i "s/- \[ \] ${padded}:/- [x] ${padded}:/" "$MASTER_TASKS" 2>/dev/null || true
    fi

    echo -e "${GREEN}  ✓ Task $task_num completed${NC}"
  else
    array_push "failed_tasks" "$task_num"
    echo -e "${RED}  ✗ Task $task_num failed (exit: $exit_code)${NC}"
    echo -e "  Check: $log_file"

    if [ -f "$BLOCKERS_DIR/task-${padded}.md" ]; then
      echo -e "${YELLOW}  Blocker report:${NC}"
      head -5 "$BLOCKERS_DIR/task-${padded}.md" | sed 's/^/    /'
    fi
  fi
  echo ""

  return $exit_code
}

cmd_run() {
  check_init

  local phase
  phase=$(get_state "phase")
  [ "$phase" = "implementation" ] || die "Not in implementation phase (current: $phase)."

  local target="${1:-next}"

  case "$target" in
    all)
      echo -e "${BOLD}Running all remaining tasks...${NC}"
      local start_time
      start_time=$(date +%s)

      while true; do
        local next
        next=$(find_next_task)
        [ "$next" -eq 0 ] && break

        run_single_task "$next" || {
          echo -e "${RED}Task $next failed. Stopping.${NC}"
          echo -e "Fix the issue then run: ./ship.sh run"
          exit 1
        }
      done

      local elapsed=$(( $(date +%s) - start_time ))
      set_state "phase" "testing"

      echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════${NC}"
      echo -e "${GREEN}  All tasks implemented! (${elapsed}s)${NC}"
      echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════${NC}"
      echo ""
      echo -e "Next: ${CYAN}./ship.sh tests${NC} → write Playwright tests"
      echo -e "Then: ${CYAN}./ship.sh verify${NC} → run and confirm"
      ;;

    next)
      local next
      next=$(find_next_task)
      if [ "$next" -eq 0 ]; then
        set_state "phase" "testing"
        echo -e "${GREEN}All tasks done. Run: ${CYAN}./ship.sh tests${NC}"
        return 0
      fi
      run_single_task "$next"
      ;;

    *)
      if [[ "$target" =~ ^[0-9]+$ ]]; then
        run_single_task "$target"
      else
        die "Invalid argument: $target. Use: run [next|all|N]"
      fi
      ;;
  esac
}

# --- Testing Phase ---

cmd_tests() {
  check_init

  local playwright_cmd
  playwright_cmd=$(get_state "playwright_cmd")
  [ "$playwright_cmd" = "null" ] && playwright_cmd="$SHIP_PLAYWRIGHT_CMD"

  echo -e "${CYAN}Launching Playwright test writing session...${NC}"
  echo -e "${DIM}Model: $SHIP_MODEL | Budget: \$$SHIP_MAX_BUDGET${NC}"
  echo ""

  claude --model "$SHIP_MODEL" --max-budget-usd "$SHIP_MAX_BUDGET" \
    "Write Playwright tests for the implemented feature.

Read these files first:
1. .ship/spec.md — acceptance criteria drive your tests
2. .ship/plan.md — understand what was built (use the file map to find implemented files)
3. .ship/context.md
4. .ship/learnings.md (if it exists — known issues to avoid in tests)

Then read the key implemented files from the plan's file map.

Your job:
- Write Playwright tests covering each acceptance criterion from the spec
- Tests verify real user flows end-to-end, not implementation internals
- Check for existing Playwright config (playwright.config.ts or similar) and follow it
- Place test files in the project's standard test location

After writing tests, run: $playwright_cmd
If tests fail due to implementation bugs, note them in .ship/learnings.md — do NOT fix the implementation.
If tests are wrong, fix the tests.

When done, update .ship/state.json: set tests_written to true and phase to 'verifying'."
}

cmd_verify() {
  check_init

  local playwright_cmd
  playwright_cmd="${SHIP_PLAYWRIGHT_CMD:-$(get_state "playwright_cmd")}"
  [ "$playwright_cmd" = "null" ] && playwright_cmd="npx playwright test"

  echo -e "${CYAN}${BOLD}Running Playwright tests...${NC}"
  echo -e "${DIM}Command: $playwright_cmd${NC}"
  echo ""

  local exit_code=0
  eval "$playwright_cmd" 2>&1 | tee "$LOGS_DIR/verify.log" || exit_code=$?

  echo ""
  if [ "$exit_code" -eq 0 ]; then
    set_state "verified" true
    set_state "phase" "complete"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  All tests pass. Feature verified!${NC}"
    echo -e "${GREEN}${BOLD}═══════════════════════════════════════════════${NC}"
  else
    set_state "verified" false
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════${NC}"
    echo -e "${RED}  Tests failed.${NC}"
    echo -e "${RED}${BOLD}═══════════════════════════════════════════════${NC}"
    echo -e "  Review: $LOGS_DIR/verify.log"
    echo -e "  Fix, then run: ${CYAN}./ship.sh verify${NC}"
  fi
  echo ""
}

# --- Utilities ---

cmd_skip() {
  check_init
  local task_num="${1:-}"
  [ -n "$task_num" ] || die "Usage: ./ship.sh skip <task-number>"

  array_push "skipped_tasks" "$task_num"

  if [ -f "$MASTER_TASKS" ]; then
    local padded
    padded=$(pad "$task_num")
    sed -i "s/- \[ \] ${padded}:/- [~] ${padded}: (skipped)/" "$MASTER_TASKS" 2>/dev/null || true
  fi

  echo -e "${YELLOW}Skipped task $task_num${NC}"
}

cmd_retry() {
  check_init
  local task_num="${1:-}"
  [ -n "$task_num" ] || die "Usage: ./ship.sh retry <task-number>"

  local tmp
  tmp=$(mktemp)
  jq ".failed_tasks -= [$task_num] | .updated_at = \"$(now)\"" "$STATE_FILE" > "$tmp"
  mv "$tmp" "$STATE_FILE"

  rm -f "$BLOCKERS_DIR/task-$(pad "$task_num").md"

  echo -e "${CYAN}Retrying task $task_num...${NC}"
  run_single_task "$task_num"
}

cmd_reset() {
  check_init
  local target="${1:-all}"

  case "$target" in
    all|requirements)
      echo -e "${YELLOW}Resetting to: requirements${NC}"
      rm -f "$SPEC_FILE" "$PLAN_FILE" "$MASTER_TASKS"
      rm -f "$TASKS_DIR"/task-*.md "$LOGS_DIR"/*.log "$BLOCKERS_DIR"/*.md
      local tmp
      tmp=$(mktemp)
      jq '.phase = "requirements" | .current_task = 0 | .total_tasks = 0 | .completed_tasks = [] | .skipped_tasks = [] | .failed_tasks = [] | .tests_written = false | .verified = false' "$STATE_FILE" > "$tmp"
      mv "$tmp" "$STATE_FILE"
      ;;
    planning)
      echo -e "${YELLOW}Resetting to: planning${NC}"
      rm -f "$PLAN_FILE" "$MASTER_TASKS"
      rm -f "$TASKS_DIR"/task-*.md "$LOGS_DIR"/*.log "$BLOCKERS_DIR"/*.md
      set_state "phase" "planning"
      ;;
    breakdown)
      echo -e "${YELLOW}Resetting to: breakdown${NC}"
      rm -f "$MASTER_TASKS"
      rm -f "$TASKS_DIR"/task-*.md "$LOGS_DIR"/*.log "$BLOCKERS_DIR"/*.md
      set_state "phase" "breakdown"
      ;;
    implementation|tasks)
      echo -e "${YELLOW}Resetting implementation progress${NC}"
      rm -f "$LOGS_DIR"/*.log "$BLOCKERS_DIR"/*.md
      local tmp2
      tmp2=$(mktemp)
      jq '.phase = "implementation" | .current_task = 1 | .completed_tasks = [] | .skipped_tasks = [] | .failed_tasks = [] | .tests_written = false | .verified = false' "$STATE_FILE" > "$tmp2"
      mv "$tmp2" "$STATE_FILE"
      if [ -f "$MASTER_TASKS" ]; then
        sed -i 's/- \[x\]/- [ ]/g; s/- \[~\]/- [ ]/g' "$MASTER_TASKS" 2>/dev/null || true
      fi
      ;;
    testing)
      echo -e "${YELLOW}Resetting to: testing${NC}"
      rm -f "$LOGS_DIR/verify.log"
      local tmp3
      tmp3=$(mktemp)
      jq '.phase = "testing" | .tests_written = false | .verified = false' "$STATE_FILE" > "$tmp3"
      mv "$tmp3" "$STATE_FILE"
      ;;
    *)
      die "Unknown phase: $target. Use: requirements|planning|breakdown|implementation|testing"
      ;;
  esac

  echo -e "${GREEN}✓ Reset complete${NC}"
  echo -e "${DIM}Note: learnings.md preserved${NC}"
}

cmd_log() {
  check_init
  local task_num="${1:-}"

  if [ -z "$task_num" ]; then
    echo -e "${BOLD}Task Logs:${NC}"
    if ls "$LOGS_DIR"/*.log &>/dev/null; then
      for f in "$LOGS_DIR"/*.log; do
        local size
        size=$(wc -c < "$f")
        echo -e "  $(basename "$f" .log)  (${size} bytes)"
      done
    else
      echo "  No logs yet."
    fi
    return
  fi

  local log_file="$LOGS_DIR/task-$(pad "$task_num").log"
  [ -f "$log_file" ] && less "$log_file" || echo -e "${YELLOW}No log for task $task_num${NC}"
}

cmd_context() {
  check_init
  if [ $# -eq 0 ]; then
    cat "$CONTEXT_FILE"
    return
  fi
  echo "- $(now): $*" >> "$CONTEXT_FILE"
  echo -e "${GREEN}✓ Added to context.md${NC}"
}

cmd_clean() {
  echo -e "${YELLOW}This will delete the .ship/ directory.${NC}"

  local tmp_learn=""
  if [ -f "$LEARNINGS_FILE" ]; then
    echo -n "Preserve learnings.md? (Y/n): "
    read -r keep_learnings
    if [ "$keep_learnings" != "n" ] && [ "$keep_learnings" != "N" ]; then
      tmp_learn=$(mktemp)
      cp "$LEARNINGS_FILE" "$tmp_learn"
    fi
  fi

  echo -n "Delete .ship/? (y/N): "
  read -r confirm
  if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    rm -rf "$SHIP_DIR"
    echo -e "${GREEN}✓ Cleaned up .ship/${NC}"
    if [ -n "$tmp_learn" ] && [ -f "$tmp_learn" ]; then
      mkdir -p "$SHIP_DIR"
      mv "$tmp_learn" "$LEARNINGS_FILE"
      echo -e "${GREEN}✓ Preserved learnings.md${NC}"
    fi
  else
    echo "Cancelled."
    [ -n "$tmp_learn" ] && [ -f "$tmp_learn" ] && rm -f "$tmp_learn"
  fi
}

cmd_help() {
  cat << 'HELPEOF'

  Ship — Spec-Driven Feature Development

  SETUP
    init [name]       Initialize ship for a new feature
    status            Show current phase and progress
    clean             Remove .ship/ (preserves learnings)
    reset [phase]     Reset to a phase (requirements|planning|breakdown|implementation|testing)

  INTERACTIVE PHASES (launches Claude Code session)
    spec              Phase 1: Requirements gathering → spec.md
    plan              Phase 2: Technical planning → plan.md
    breakdown         Phase 3: Task breakdown → task files

  AUTOMATED IMPLEMENTATION (isolated sub-agents)
    run [next]        Execute next incomplete task
    run <N>           Execute specific task
    run all           Execute all remaining tasks

  PLAYWRIGHT TESTING
    tests             Write Playwright tests from spec (one agent session)
    verify            Run Playwright test suite (shell only, no agent)

  UTILITIES
    retry <N>         Retry a failed task
    skip <N>          Skip a task
    log [N]           List logs or view log for task N
    context [note]    View or append to context.md
    help              Show this help

  ENVIRONMENT VARIABLES
    SHIP_MODEL           Model for all agents (default: sonnet)
    SHIP_MAX_BUDGET      Max USD per agent session (default: 2.00)
    SHIP_PLAYWRIGHT_CMD  Playwright command (default: npx playwright test)
    SHIP_CLAUDE_FLAGS    Extra claude CLI flags

  FLOW
    ./ship.sh init my-feature
    ./ship.sh spec
    ./ship.sh plan
    ./ship.sh breakdown
    ./ship.sh run all      → implement everything
    ./ship.sh tests        → write Playwright tests from spec
    ./ship.sh verify       → run tests, confirm complete

HELPEOF
}

# --- Main ---

trap 'echo -e "\n${YELLOW}Interrupted. State saved in .ship/state.json${NC}"; exit 130' INT

check_deps

case "${1:-help}" in
  init)           cmd_init "${2:-}" ;;
  status|st)      cmd_status ;;
  spec)           cmd_spec ;;
  plan)           cmd_plan ;;
  breakdown)      cmd_breakdown ;;
  run)            cmd_run "${2:-next}" ;;
  tests)          cmd_tests ;;
  verify)         cmd_verify ;;
  retry)          cmd_retry "${2:-}" ;;
  skip)           cmd_skip "${2:-}" ;;
  reset)          cmd_reset "${2:-all}" ;;
  log|logs)       cmd_log "${2:-}" ;;
  context)        shift; cmd_context "$@" ;;
  clean)          cmd_clean ;;
  help|-h|--help) cmd_help ;;
  *)              echo -e "${RED}Unknown: $1${NC}"; cmd_help; exit 1 ;;
esac
