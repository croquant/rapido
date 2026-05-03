---
description: Plans the implementation for a GitHub issue by finding and reviewing relevant documentation.
argument-hint: [issue-number-or-url]
arguments: ISSUE
disable-model-invocation: true
---

Please analyze and plan the implementation for the following GitHub issue: $ISSUE

Context Gathering:

1. Read the provided issue description carefully.
2. Based on the issue's context, search for and review the most relevant whitepaper(s) or documentation located in the `docs/` directory.

Instructions:

1. Propose a high-level, step-by-step implementation plan based on the issue and the documentation you found.
2. Suggest improvements: If you see a better approach that deviates slightly from the established documentation, please suggest it. Explicitly highlight any deviations and explain your rationale.
3. Before writing any code, please list out any clarifying questions you have or missing context you need to proceed effectively.
