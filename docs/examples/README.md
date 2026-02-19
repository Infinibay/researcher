# Example Projects

This directory contains worked examples showing how to use PABADA's multi-agent project management system.

## Available Examples

### [example-web-app-project.md](./example-web-app-project.md)

A complete walkthrough of building a "Simple Todo API" project using PABADA. Covers:

- Project creation and planning
- Epic and milestone structure
- Task lifecycle (backlog -> done)
- Research and code task types
- Dependency management
- Code review flow
- Rejection and retry cycle
- Brainstorming sessions
- Completion detection

## Running the Examples

1. Start the PABADA API server
2. Follow the steps in each example document
3. Use either the REST API directly or the frontend UI

## Test Coverage

The integration test suite at `backend/tests/integration/test_full_lifecycle.py` exercises the same lifecycle paths described in these examples, using the real tool layer and database.
