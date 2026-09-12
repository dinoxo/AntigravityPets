# Antigravity Pets 🐾

An interactive, animated floating desktop companion system designed for **Google Antigravity** and modern AI coding agents. Antigravity Pets connects the agent's real-time execution loop directly to an animated desktop companion that visually reacts to tool calls, background thinking, verification reviews, failures, and task completions with sub-millisecond latency.

Fully compatible with the **Codex Pets** spritesheet specification (v1 and v2 grids).

---

## 🌟 Key Features

- **⚡ Zero-Overhead IPC Pipeline**: Non-blocking UDP datagram transport over `127.0.0.1:41738`. Synchronous hooks complete in < 1ms, well below Antigravity's 20ms SLA ceiling.
- **💬 Adaptive Floating HUD Capsule**: Dynamically calculates text dimensions and wraps long agent commands, file paths, and messages across multiple lines without truncating or obscuring the pet.
- **🖥️ Dual Desktop Hosts**:
  - **Windows & Linux (Cross-Platform)**: PySide6 (Qt6) overlay utilizing Desktop Window Manager (DWM) alpha blending (`WA_TranslucentBackground`), frameless design, context menus, and Windows system chime audio.
  - **macOS (Native)**: Zero-dependency Swift AppKit host compiled with hardware-accelerated CoreAnimation.
- **🎨 Codex Spritesheet Engine**: Automatic frame detection across standard 8-column grids (192 × 208 px cells) to prevent blank-frame flicker.
- **👩‍🏫 Cochepa & Bundled Pets**: Includes the beloved **Cochepa** (Spanish teacher companion with 10 animation rows including coffee sipping, reading Don Quijote, and whiteboard teaching), **Default Bot**, and **Leia Dog**.
- **🔊 Sound Feedback**: Audio cues via native system chimes for task success, errors, and interactive actions.
- **🌐 Full Spanish Localization**: Native Spanish translations for agent actions, statuses, and teacher interactions.

---

## 🏗️ Architecture & Technologies

Antigravity Pets is built with a modular, layered architecture:

```
+--------------------------------------------------------+
|                   Google Antigravity                   |
|             (Agent Lifecycle Execution Loop)           |
+---------------------------+----------------------------+
                            | Synchronous Hook Runner (<20ms SLA)
                            v
+--------------------------------------------------------+
|              .agents/hooks.json                        |
|       maps PreToolUse, PostToolUse, Stop, etc.         |
+---------------------------+----------------------------+
                            v
+--------------------------------------------------------+
|            dispatcher/dispatch_hook.py                 |
|      - Formats JSON event envelope                     |
|      - Non-blocking UDP fire-and-forget socket         |
+---------------------------+----------------------------+
                            | UDP 127.0.0.1:41738 (<1ms)
                            v
+--------------------------------------------------------+
|                 Desktop Overlay Hosts                  |
|                                                        |
|   Windows / Linux (PySide6)      macOS (Swift AppKit)  |
|   +-----------------------+      +------------------+  |
|   |   desktop_py/app.py   |      |  desktop_swift/  |  |
|   |   - IPC Server        |      |  - Native Host   |  |
|   |   - State Machine     |      |  - CoreAnimation |  |
|   |   - Adaptive HUD      |      +------------------+  |
|   |   - Winsound Chimes   |                            |
|   +-----------------------+                            |
+--------------------------------------------------------+
```

### Technology Stack
- **Languages**: Python 3.9+ (Core Engine, Dispatcher, PySide6 Host), Swift 5+ (macOS Native Host), Batch scripting (Windows launchers).
- **GUI Frameworks**:
  - **PySide6 / PyQt6**: Transparent frameless canvas, antialiased vector painting, dynamic typography metrics (`QFontMetrics`).
  - **Swift / Cocoa AppKit**: Native macOS floating window panel (`NSPanel`, `wantsLayer = true`).
- **Networking / IPC**: Local loopback UDP sockets (`socket.AF_INET, SOCK_DGRAM`), fire-and-forget architecture with zero disk locking or network blocking.
- **Graphics & Assets**: Pillow (PIL) for spritesheet validation and grid processing; supports Codex 8x9 (v1) and 8x11 (v2) formats at 192x208 px per frame.
- **Testing**: Python `unittest` suite with automated IPC latency benchmarks (1,000 synthetic events).

---

## 📋 Lifecycle Event & State Mapping

The core state machine (`core/state_machine.py`) seamlessly translates Antigravity agent lifecycle hooks into standard Codex spritesheet rows:

| Antigravity Event | State | Codex Row | Behavior & Visual Representation |
| :--- | :--- | :--- | :--- |
| **Idle / Resting** | `idle` | Row 0 | Default breathing loop; HUD auto-fades after 3.5s |
| **Window Drag (dx < 0)** | `move_left` | Row 1 | Walking left animation |
| **Window Drag (dx > 0)** | `move_right` | Row 2 | Walking right animation |
| **Stop (Clean Success)** | `jump` | Row 3 | Celebratory jump (2.5s transient) |
| **Greeting / Interaction** | `wave` | Row 4 | Friendly greeting wave (2.5s transient) |
| **PostToolUse (Error)** | `failed` | Row 5 | Error shake / dizzy expression (3.0s transient) |
| **PostInvocation** | `waiting` | Row 6 | Pauses, awaiting human input |
| **PreToolUse / Thinking** | `working` | Row 7 | Typing / executing shell command or model thinking |
| **PostToolUse (Success)** | `review` | Row 8 | Inspecting changes / reviewing verification steps |
| **Interactive Coffee** | `coffee` | Row 9 | Taking a sip and savoring coffee (3.5s transient) |

---

## 🚀 Quick Start

### 🪟 Windows Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/dinoxo/AntigravityPets.git
   cd AntigravityPets
   ```
2. Double-click `run_windows.bat` or run in terminal:
   ```cmd
   run_windows.bat
   ```
3. *(Optional)* Build a standalone single-file `.exe` (no Python required on target machines):
   ```cmd
   scripts\build_windows_exe.bat
   ```
   Output binary is saved to `dist\AntigravityPets.exe`.

### 🍎 macOS Setup
Run the precompiled native AppKit binary:
```bash
./bin/antigravity-pets-native
```
Or recompile from source with zero external dependencies:
```bash
swiftc -O -framework Cocoa desktop_swift/Sources/main.swift -o bin/antigravity-pets-native
```

### 🐧 Linux Setup
```bash
pip install -r desktop_py/requirements.txt
python3 desktop_py/app.py
```

---

## 🎮 Interactive Controls

- **Drag & Drop**: Left-click and drag the pet anywhere on your screen. Walking animations trigger automatically based on drag vector direction.
- **Double-Click**: Quickly triggers a fun interaction (coffee break, greeting, or wise quote).
- **Right-Click Context Menu**:
  - **Acciones**:
    - ☕ **Tomar Café**: Smooth 4-stage drinking animation with witty teacher quotes.
    - 👋 **Saludar**: Friendly wave greeting.
    - 📖 **Leer Don Quijote**: Classical literary quotes.
    - 🧑‍🏫 **Explicar en Pizarra**: Software engineering & architecture concepts.
    - 💻 **Trabajar / Pensar**: Coding and refactoring pose.
    - 🎉 **Festejar Éxito**: Celebration jump.
    - ⏰ **Consultar Hora**: Live system clock display.
  - **🔊 Sonidos del Sistema**: Toggle Windows system audio chimes on/off.
  - **Pets**: Switch in real-time between Cochepa, Default Bot, Leia, or custom pets.
  - **Scale**: Choose between `1.0x` (192x208 px), `1.5x` (288x312 px), or `2.0x` (384x416 px).
  - **Reset Position**: Returns the companion to the bottom-right corner of your primary display.
  - **Quit**: Closes the application.

---

## 🔌 Connecting to Any Antigravity Project

To monitor an agent working on any repository:
1. Keep Antigravity Pets running on your desktop (`run_windows.bat` or native Mac binary).
2. Copy the `.agents/` folder and `dispatcher/` folder to your project root:
   ```bash
   cp -r .agents /path/to/your/project/
   cp -r dispatcher /path/to/your/project/
   ```
3. Whenever Google Antigravity executes tools or models in that repository, your desktop pet will react live!

---

## 🧪 Testing & Verification

Run the full automated test suite and latency benchmark:
```bash
python -m unittest discover tests
```

Test animations interactively without launching an agent:
```bash
python scripts/simulate_agent.py
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
