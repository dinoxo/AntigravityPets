# AGENTS.md — Antigravity Pets Development & Engineering Guidelines

## Role & Project Purpose
You are maintaining and extending the **Antigravity Pets** companion system for Google Antigravity. It connects the agent execution loop directly to an animated floating desktop companion reacting visually to tool executions, model thinking, verification reviews, failures, and task completion.

The repository consists of:
1. **Antigravity Hook Integration**: `.agents/hooks.json` mapping agent lifecycle events to `dispatcher/dispatch_hook.py`.
2. **IPC Transport Layer**: Low-latency UDP datagram pipeline on `127.0.0.1:41738`.
3. **Core Engine**: State machine (`core/state_machine.py`) and Codex asset loader (`core/asset_loader.py`).
4. **Desktop Overlay Clients**:
   - **macOS (Native)**: Zero-dependency Swift AppKit host (`desktop_swift/Sources/main.swift` -> `bin/antigravity-pets-native`).
   - **Windows / Linux (Cross-Platform)**: PySide6 host (`desktop_py/app.py` -> `run_windows.bat` or standalone `.exe`).

---

## Critical Technical Constraints

### 1. Hook Latency & Safety SLA (< 20ms ceiling, < 1ms actual)
- Antigravity lifecycle hooks execute synchronously on every agent action and block the execution loop.
- `dispatcher/dispatch_hook.py` MUST NEVER perform disk file locking, heavy parsing, blocking network lookups, or slow operations.
- Uses fire-and-forget UDP socket to `127.0.0.1:41738`.
- If the desktop client is inactive or offline, the dispatcher MUST silently drop packets without throwing exceptions or delaying execution.
- **Contract Output**:
  - `PreToolUse`: Must write `{"decision": "allow"}\n` to stdout.
  - `PostToolUse`, `PreInvocation`, `PostInvocation`, `Stop`: Must write `{}\n` to stdout.
- **Fail-Safe Guarantee**: Top-level exception handlers must ensure `dispatch_hook.py` always prints the required JSON response and exits with code 0.
- **Working Directory (CWD) Rule**: Antigravity executes hooks with CWD set to the directory containing `hooks.json` (`.agents/`). The `.agents/dispatcher` symlink must be preserved so `python3 dispatcher/dispatch_hook.py` resolves accurately.

### 2. IPC Message Protocol Schema
Every datagram sent over IPC must be a JSON object with this structure:
```json
{
  "event": "PreToolUse" | "PostToolUse" | "PreInvocation" | "PostInvocation" | "Stop",
  "timestamp": 1726057200.123,
  "tool": "run_command" | "write_to_file" | null,
  "error": null | "error message string",
  "title": "Running Command" | "Thinking..." | "Completed" | null,
  "detail": "npm test" | "app.py" | null
}
```

### 3. Codex Asset Compatibility
- **Dimensions**: Standard cell size is **192 × 208 px** per frame.
- **Grid Layouts**:
  - **Codex v1**: 8 columns × 9 rows (`1536 × 1872 px`).
  - **Codex v2**: 8 columns × 11 rows (`1536 × 2288 px`, rows 9–10 contain 16 gaze directions).
- **Dynamic Frame Detection**: Spritesheets often have fewer than 8 frames for certain actions (e.g. `idle` having 7 frames, `jump` having 4 frames). The asset loader must auto-detect valid non-empty frames by scanning column alphas to prevent blank-frame blinking/flickering.
- **Search Paths**:
  1. `~/.antigravity/pets/<slug>/`
  2. `~/.codex/pets/<slug>/` (native compatibility with *Awesome Codex Pet* and *Petdex*)
  3. Bundled `assets/pets/<slug>/`

### 4. State Machine & Codex Row Mapping
Transitions map Antigravity lifecycle events to standard Codex rows:

| Antigravity Event | State | Codex Row | Behavior / Notes |
| :--- | :--- | :--- | :--- |
| Loop idle / Resting | `idle` | Row 0 | Default breathing loop; HUD auto-fades after 3.5s |
| Window drag vector $dx < 0$ | `move_left` | Row 1 | Walking left animation |
| Window drag vector $dx > 0$ | `move_right` | Row 2 | Walking right animation |
| `Stop` (success) | `jump` | Row 3 | Celebratory jump (transient 2.5s, reverts to `idle`) |
| Farewell / greeting | `wave` | Row 4 | Transient wave (2.5s) |
| `PostToolUse` (with error) | `failed` | Row 5 | Dizzy/slumped shake (transient 3.0s) |
| `PostInvocation` (waiting user) | `waiting` | Row 6 | Pauses, awaiting input |
| `PreToolUse` / `PreInvocation` | `working` | Row 7 | Typing / executing action |
| `PostToolUse` (clean success) | `review` | Row 8 | Inspecting changes / verification |

### 5. Floating HUD Capsule Requirements
- Rendered directly above the pet sprite with a dark translucent capsule (`#1c2028` at ~88% opacity, 1px subtle white border).
- Line 1: Bold title (`Executing Command`, `Editing File`, `Thinking...`, `Reviewing`).
- Line 2: Subtitle detail (command string, file name, or search query).
- Auto-fades when returning to `idle`.

---

## Operating Systems & Clients

### macOS Host (`desktop_swift/`)
- Native AppKit application written in Swift.
- Zero dependencies; uses hardware-accelerated CoreAnimation (`wantsLayer = true`).
- Compile command:
  ```bash
  swiftc -O -framework Cocoa desktop_swift/Sources/main.swift -o bin/antigravity-pets-native
  ```

### Windows Host (`desktop_py/`)
- Cross-platform overlay written in Python using PySide6.
- Uses Windows Desktop Window Manager (DWM) alpha blending via `WA_TranslucentBackground` and `Qt.WindowType.Tool`.
- Launch command:
  ```cmd
  run_windows.bat
  ```
- Standalone single-file `.exe` build:
  ```cmd
  scripts\build_windows_exe.bat
  ```

---

## Verification & Testing Suite

When modifying any part of the system, run:
1. **Automated Unit Tests & Latency Benchmark**:
   ```bash
   python3 -m unittest discover tests
   ```
   (Must pass all 18 tests; median IPC latency must remain < 5ms).
2. **Interactive Simulation**:
   ```bash
   ./scripts/simulate_agent.py
   ```
