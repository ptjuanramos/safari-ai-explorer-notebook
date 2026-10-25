---
name: commit-message
description: Generate a git commit message from the staged changes. Use when the user asks for a commit message or invokes /commit-message. Pass "commit" as an argument to also create the commit.
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git commit:*)
---

# Commit message generator

## Context

Status:
!`git status --short`

Staged changes:
!`git diff --cached --stat`

!`git diff --cached`

Recent commits:
!`git log --oneline -10`

## Task

Write a commit message for the staged changes above. Use only this context — do not run extra commands or scripts to inspect the changes.

- If nothing is staged, say so and stop.
- In `.ipynb` diffs, only `"source"` changes matter. Ignore outputs, execution counts and metadata.
- Summary line: imperative mood ("Add…", not "Added…"), ≤ 72 chars, no trailing period.
- Body (optional): wrap at 72 chars, explain what and why. Don't invent motivation not visible in the diff.
- If the changes are unrelated, suggest splitting them, with one message per commit.

Print the message in one fenced code block.

If the argument is `commit` ($ARGUMENTS), run `git commit` with that message, then `git log --oneline -1`. Otherwise don't commit.
