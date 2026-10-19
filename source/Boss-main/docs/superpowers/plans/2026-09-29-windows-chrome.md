# Windows Chrome connection

Goal: Detect and attach to an existing authenticated BOSS recruiter tab on Windows, following the original boss-resume-filter CDP approach.

Architecture: Local Chrome discovery and read-only DOM authentication probe; persisted endpoint and target binding; independent managed profile fallback; browser actions selected on Windows. Detach without closing external Chrome.

Tech stack: FastAPI, SQLAlchemy/SQLite, Playwright CDP, React/TypeScript.

Spec: User requested Windows adaptation and reuse of logged-in Chrome. Ordinary Chrome without CDP cannot be attached; Chrome 136+ requires a non-default profile for remote debugging. Do not move/copy cookies or restart ordinary Chrome. Browser chat/attachment collection remains unsupported and must be visible.

1. Write failing tests for loopback endpoints, BOSS host/login checks and platform selection.
2. Implement discovery, connection, managed launch and additive account migration.
3. Add account discovery UI, error reporting and task account selection.
4. Bind browser task runtime; verify greeting once with DOM fixtures only.
5. Run unit/integration tests, build frontend, restart local server and check UI. No live recruiting messages during validation.

## Existing ordinary Chrome (user constraint)
The user explicitly forbids opening or restarting Chrome. Add a Manifest V3 extension, loaded manually into the existing browser once. Pair over a token-authenticated loopback WebSocket. No cookie access, remote API, debugger permission, arbitrary evaluation, or new tabs. Inspect actual DOM in existing BOSS tabs; preserve tab and document identities and reuse the same task/account path. Connection and discovery are read-only. Commands are finite: inspect, cards, greet once, scroll. Test worker with Chrome API mocks and DOM fixtures; actual existing-browser installation requires user action.
