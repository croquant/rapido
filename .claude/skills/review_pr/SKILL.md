---
description: Performs a comprehensive code review of a GitHub Pull Request and posts comments via the GitHub CLI.
argument-hint: [PR number or url]
arguments: pr
disable-model-invocation: true
---

Please perform a deep and comprehensive review of the following pull request: $pr

Context Gathering:

1. Use the GitHub CLI (`gh pr view $pr` and `gh pr diff $pr`) to read the PR description, understand its goal, and analyze the changed files.

Review Criteria:
Evaluate the code specifically for:

- Logic errors, unhandled edge cases, and potential bugs.
- Performance bottlenecks or security vulnerabilities.
- Architectural alignment with the existing codebase.
  (Skip minor styling nitpicks unless they violate severe readability standards).

Action:

1. Local Summary: First, summarize your core findings and feedback to me here in the chat.
2. PR Comments: Once you have formulated your feedback, use the GitHub CLI to post constructive comments directly to the PR. Use inline comments for specific line issues, and a general review comment for overall architectural feedback.
