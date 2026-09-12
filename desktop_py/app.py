"""Python Desktop Companion overlay for Antigravity Pets using PySide6/PyQt."""

import datetime
import os
import random
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import winsound
except ImportError:
    winsound = None


def play_sound_async(sound_type: str = "chime") -> None:
    """Play a non-blocking Windows system chime / notification sound."""
    if not winsound:
        return
    def _play():
        try:
            if sound_type == "chime":
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            elif sound_type == "error":
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sound_type == "ok":
                winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            pass
    t = threading.Thread(target=_play, daemon=True)
    t.start()


SPANISH_TRANSLATIONS = {
    "thinking...": "Pensando...",
    "waiting": "Esperando respuesta",
    "running command": "Ejecutando comando",
    "writing file": "Creando archivo",
    "editing file": "Editando archivo",
    "reading file": "Leyendo archivo",
    "searching code": "Buscando en código",
    "completed": "¡Tarea completada!",
    "failed": "Error en comando",
    "review": "Revisando cambios",
    "idle": "En reposo",
    "move_left": "Caminando",
    "move_right": "Caminando",
    "jump": "¡Festejando!",
    "wave": "¡Hola!",
    "coffee": "Tomando café",
    "analyzing context & planning": "Analizando contexto y plan",
    "awaiting user response": "Esperando tu respuesta",
    "executing shell command": "Ejecutando en consola",
    "grep search": "Búsqueda en código",
    "task completed cleanly": "Tarea finalizada con éxito",
    "reviewing": "Revisando cambios",
    "finding files": "Buscando archivos",
    "searching web": "Buscando en la web",
    "fetching url": "Consultando URL",
    "asking question": "Esperando tu respuesta",
    "stopped with error": "Detenido con error",
    "task completed": "¡Tarea completada!",
    "all goals finished!": "¡Todo terminado con éxito!",
    "tool failed": "Error en herramienta",
    "waiting for your answer": "Esperando tu respuesta",
}


def translate_text(text: str) -> str:
    """Translate HUD titles and details to natural Spanish."""
    if not text:
        return text
    low = text.lower().strip()
    if low in SPANISH_TRANSLATIONS:
        return SPANISH_TRANSLATIONS[low]
    for k, v in SPANISH_TRANSLATIONS.items():
        if k in low:
            text = text.replace(k.title(), v).replace(k, v)
    if text.startswith("Executing "):
        return text.replace("Executing ", "Ejecutando ")
    if text.endswith(" completed"):
        return text.replace(" completed", " completado")
    return text

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.asset_loader import AssetLoader, PetPackage
from core.state_machine import PetState, PetStateMachine
from ipc.protocol import EventPacket
from ipc.server import IPCServer


def run_qt_app() -> None:
    try:
        from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
        from PySide6.QtGui import QAction, QContextMenuEvent, QMouseEvent, QPainter, QPixmap
        from PySide6.QtWidgets import QApplication, QMenu, QWidget
    except ImportError:
        try:
            from PyQt6.QtCore import QPoint, QRect, Qt, QTimer, pyqtSignal as Signal
            from PyQt6.QtGui import QAction, QContextMenuEvent, QMouseEvent, QPainter, QPixmap
            from PyQt6.QtWidgets import QApplication, QMenu, QWidget
        except ImportError:
            print("Neither PySide6 nor PyQt6 is installed.")
            print("On macOS, you can run the native zero-dependency binary:")
            print("  ./bin/antigravity-pets-native")
            print("Or install PySide6:")
            print("  pip install -r desktop_py/requirements.txt")
            sys.exit(1)

    class PetOverlayWidget(QWidget):
        event_received_signal = Signal(object)

        def __init__(self, loader: AssetLoader, initial_pet: str = "default") -> None:
            super().__init__()
            self.loader = loader
            self.state_machine = PetStateMachine()
            self.current_frame = 0
            self.scale_factor = 1.0

            # Window setup: frameless, transparent, stays on top
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

            self.drag_position: Optional[QPoint] = None

            # Sound & Interactivity
            self.sounds_enabled: bool = True
            self.interaction_quote: Optional[str] = None
            self.interaction_title: Optional[str] = None
            self.coffee_count: int = 0
            self.interaction_revert_timer = QTimer(self)
            self.interaction_revert_timer.setSingleShot(True)
            self.interaction_revert_timer.timeout.connect(self._revert_interaction)

            # Timer to gracefully return to IDLE and show clock when agent is idle/waiting
            self.agent_idle_timer = QTimer(self)
            self.agent_idle_timer.setSingleShot(True)
            self.agent_idle_timer.timeout.connect(self._on_agent_inactivity)

            # Load pet package
            self.pet_package: Optional[PetPackage] = None
            self.pixmap: Optional[QPixmap] = None
            self.load_pet(initial_pet)

            # Animation timer
            self.anim_timer = QTimer(self)
            self.anim_timer.timeout.connect(self.advance_frame)
            self.update_animation_speed()
            self.anim_timer.start()

            # IPC Server
            self.ipc_server = IPCServer()
            self.ipc_server.register_callback(self._on_ipc_event)
            self.ipc_server.start()

            self.event_received_signal.connect(self._handle_event_in_main_thread)

            # Position at bottom-right of screen
            self.update_geometry()
            self.reset_position()

        def load_pet(self, slug: str) -> None:
            try:
                pkg = self.loader.load_pet(slug)
                self.pet_package = pkg
                self.pixmap = QPixmap(str(pkg.spritesheet_path))

                # Auto-detect valid frame counts to prevent blank-frame flicker (e.g. Leia v2)
                qimg = self.pixmap.toImage()
                for state, anim in pkg.animations.items():
                    r = anim.row
                    last_col = 0
                    for col in range(pkg.columns - 1, -1, -1):
                        start_x = col * pkg.cell_width
                        start_y = r * pkg.cell_height
                        has_content = False
                        mid_x = start_x + pkg.cell_width // 2
                        for dy in range(20, pkg.cell_height - 20, 10):
                            y = start_y + dy
                            if mid_x < qimg.width() and y < qimg.height() and qimg.pixelColor(mid_x, y).alpha() > 12:
                                has_content = True
                                break
                        if has_content:
                            last_col = col
                            break
                    anim.frames = max(1, last_col + 1)

                self.update_geometry()
                self.update()
            except Exception as e:
                print(f"Error loading pet '{slug}': {e}")

        def update_geometry(self) -> None:
            if not self.pet_package:
                return
            hud_h = int(90 * self.scale_factor)
            w = int(max(self.pet_package.cell_width * self.scale_factor, 320 * self.scale_factor))
            h = int(self.pet_package.cell_height * self.scale_factor + hud_h)
            self.resize(w, h)

        def set_scale(self, scale: float) -> None:
            self.scale_factor = scale
            self.update_geometry()
            self.update()

        def update_animation_speed(self) -> None:
            if not self.pet_package:
                self.anim_timer.setInterval(200)
                return
            state = self.state_machine.current_state
            anim = self.pet_package.animations.get(state)
            fps = anim.fps if anim and anim.fps > 0 else self.pet_package.default_fps
            fps = max(1, min(fps, 60))
            interval_ms = int(1000 / fps)
            if self.anim_timer.interval() != interval_ms:
                self.anim_timer.setInterval(interval_ms)

        def advance_frame(self) -> None:
            if not self.pet_package:
                return
            self.update_animation_speed()
            state = self.state_machine.current_state
            anim = self.pet_package.animations.get(state)
            max_frames = anim.frames if anim else self.pet_package.columns
            self.current_frame = (self.current_frame + 1) % max(1, max_frames)
            self.update()

        def paintEvent(self, event) -> None:
            if not self.pet_package or not self.pixmap:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            hud_h = int(90 * self.scale_factor)
            pet_w = int(self.pet_package.cell_width * self.scale_factor)
            pet_h = int(self.pet_package.cell_height * self.scale_factor)
            pet_x = (self.width() - pet_w) // 2

            # 1. Draw Pet Sprite
            state = self.state_machine.current_state
            x, y, w, h = self.pet_package.get_frame_rect(state, self.current_frame)
            source_rect = QRect(x, y, w, h)
            target_rect = QRect(pet_x, hud_h, pet_w, pet_h)
            painter.drawPixmap(target_rect, self.pixmap, source_rect)

            # 2. Draw Floating HUD Capsule Bubble
            now_str = datetime.now().strftime("%H:%M")
            if self.interaction_quote:
                title = self.interaction_title or f"⏰ {now_str} hs"
                detail = self.interaction_quote
            elif state == PetState.IDLE and not self.state_machine.current_title:
                title = f"⏰ {now_str} hs"
                detail = "Cochepa en reposo"
            else:
                raw_title = self.state_machine.current_title or state.value.title()
                raw_detail = self.state_machine.current_detail or ""
                title = translate_text(raw_title)
                detail = translate_text(raw_detail)

            from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPen

            title_font = QFont()
            title_font.setPointSize(int(9 * min(self.scale_factor, 1.4)))
            title_font.setBold(True)
            title_fm = QFontMetrics(title_font)
            title_w = title_fm.horizontalAdvance(title)
            title_h = title_fm.height()

            detail_font = QFont()
            detail_font.setPointSize(int(8 * min(self.scale_factor, 1.4)))
            detail_fm = QFontMetrics(detail_font)

            padding_x = int(12 * self.scale_factor)
            max_pill_w = self.width() - 16
            max_inner_w = max_pill_w - (padding_x * 2)

            detail_clean = detail.strip() if detail else ""
            if detail_clean:
                raw_detail_w = detail_fm.horizontalAdvance(detail_clean)
                if raw_detail_w <= max_inner_w:
                    desired_w = max(title_w, raw_detail_w)
                    pill_w = max(int(150 * self.scale_factor), min(max_pill_w, desired_w + padding_x * 2 + 12))
                else:
                    pill_w = max_pill_w
                inner_w = pill_w - (padding_x * 2)
                detail_bound = detail_fm.boundingRect(
                    QRect(0, 0, inner_w, 200),
                    int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter),
                    detail_clean,
                )
                max_detail_h = hud_h - 22 - title_h
                detail_h = max(int(14 * self.scale_factor), min(detail_bound.height(), max_detail_h))
                pill_h = 6 + title_h + 3 + detail_h + 6
            else:
                pill_w = max(int(130 * self.scale_factor), min(max_pill_w, title_w + padding_x * 2 + 12))
                pill_h = title_h + 14
                detail_h = 0

            pill_x = (self.width() - pill_w) // 2
            pill_y = hud_h - pill_h - 4
            corner_r = min(14, pill_h // 2)

            # Dark translucent pill background with subtle glass border
            painter.setBrush(QBrush(QColor(24, 28, 36, 230)))
            painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
            painter.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, corner_r, corner_r)

            # Title text
            painter.setFont(title_font)
            painter.setPen(QColor(255, 255, 255, 245))
            if detail_clean:
                title_rect = QRect(pill_x + padding_x, pill_y + 6, pill_w - (padding_x * 2), title_h)
                painter.drawText(title_rect, int(Qt.AlignmentFlag.AlignCenter), title)

                # Detail text with multi-line word wrapping
                painter.setFont(detail_font)
                painter.setPen(QColor(215, 220, 230, 225))
                detail_y = pill_y + 6 + title_h + 2
                detail_draw_rect = QRect(pill_x + padding_x, detail_y, pill_w - (padding_x * 2), detail_h)
                painter.drawText(
                    detail_draw_rect,
                    int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignCenter),
                    detail_clean,
                )
            else:
                # Vertically centered title
                title_rect = QRect(pill_x + padding_x, pill_y, pill_w - (padding_x * 2), pill_h)
                painter.drawText(title_rect, int(Qt.AlignmentFlag.AlignCenter), title)

        def trigger_interaction(self, action: str = "saludo") -> None:
            """Trigger an interactive animation, sound, and witty Spanish teacher quote."""
            now_str = datetime.now().strftime("%H:%M")
            if action == "cafe":
                target_state = PetState.COFFEE
                self.interaction_title = "☕ Tomando Café"
                self.coffee_count += 1
                quotes = [
                    f"«¡Qué bendición de café! (Taza #{self.coffee_count}) Tomando un sorbito...»",
                    "«El balance perfecto entre cafeína y buenas prácticas.»",
                    "«¡La cafeína pegó en el ángulo! Lista para seguir programando.»",
                    "«Saboreando con calma... La cafeína enciende las neuronas.»",
                ]
            elif action == "saludo":
                target_state = PetState.WAVE
                self.interaction_title = "👋 Saludo Cordial"
                quotes = [
                    "«¡Hola! Lista con el Quijote y las clases de castellano.»",
                    "«¡Buenos días! ¿Qué vamos a programar hoy?»",
                    "«¡Un saludo cordial! Recordá escribir código limpio y sin faltas.»",
                ]
            elif action == "quijote":
                target_state = PetState.WAITING
                self.interaction_title = "📖 Don Quijote"
                quotes = [
                    "«Confía en el tiempo, que suele dar dulces salidas a amargas dificultades.»",
                    "«La razón de la sinrazón que a mi razón se hace...»",
                    "«El que lee mucho y anda mucho, ve mucho y sabe mucho.»",
                    "«La pluma es la lengua del alma; tales fueren los conceptos, tales los escritos.»",
                ]
            elif action == "pizarra":
                target_state = PetState.REVIEW
                self.interaction_title = "🧑‍🏫 En la Pizarra"
                quotes = [
                    "«¡Atención a la pizarra! Arquitectura limpia y modular ante todo.»",
                    "«Explicando los fundamentos: conceptos antes de escribir código.»",
                    "«¡Miren bien el diagrama en la pizarra, nada de atajos!»",
                ]
            elif action == "laptop":
                target_state = PetState.WORKING
                self.interaction_title = "💻 Pensando / Programando"
                quotes = [
                    "«¡Ajá! Se me acaba de ocurrir una excelente idea de refactor.»",
                    "«Escribiendo algoritmos eficientes en la laptop...»",
                ]
            elif action == "festejo":
                target_state = PetState.JUMP
                self.interaction_title = "🎉 ¡Festejo de Éxito!"
                quotes = [
                    "«¡Éxito total! ¡Pruebas pasadas y sin errores!»",
                    "«¡Excelente trabajo! Un diez rotundo para el equipo.»",
                ]
            elif action == "hora":
                target_state = PetState.IDLE
                self.interaction_title = f"⏰ {now_str} hs"
                quotes = [
                    f"«La hora oficial es {now_str} hs. El tiempo vuela cuando programamos bien.»",
                    f"«Son las {now_str} hs. Buen momento para una pausa y revisar la arquitectura.»",
                ]
            else:
                target_state = PetState.WAVE
                self.interaction_title = "👋 Saludo"
                quotes = ["«Sombra o gigante, ¡a resolver ese bug!»"]

            self.interaction_quote = random.choice(quotes)
            if self.sounds_enabled:
                play_sound_async("ok")

            self.state_machine.set_state(target_state, schedule_revert=False)
            self.interaction_revert_timer.start(4500)
            self.update()

        def _revert_interaction(self) -> None:
            self.interaction_quote = None
            self.interaction_title = None
            self.state_machine.set_state(PetState.IDLE, schedule_revert=False)
            with self.state_machine._lock:
                self.state_machine._current_title = None
                self.state_machine._current_detail = None
            self.update()

        def _on_agent_inactivity(self) -> None:
            """Gracefully return to IDLE breathing with the clock after waiting or reviewing."""
            if self.state_machine.current_state in (PetState.WAITING, PetState.REVIEW):
                self.state_machine.set_state(PetState.IDLE, schedule_revert=False)
                with self.state_machine._lock:
                    self.state_machine._current_title = None
                    self.state_machine._current_detail = None
                self.update()

        def toggle_sounds(self, enabled: bool) -> None:
            self.sounds_enabled = enabled

        def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                # Double click alternates between a greeting, coffee, or advice
                choice = random.choice(["cafe", "saludo", "quijote"])
                self.trigger_interaction(choice)
                event.accept()

        def mousePressEvent(self, event: QMouseEvent) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

        def mouseMoveEvent(self, event: QMouseEvent) -> None:
            if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
                new_pos = event.globalPosition().toPoint() - self.drag_position
                dx = new_pos.x() - self.x()
                self.move(new_pos)
                self.state_machine.handle_drag(dx, 0)
                event.accept()

        def mouseReleaseEvent(self, event: QMouseEvent) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_position = None
                self.state_machine.handle_drag_end()
                event.accept()

        def contextMenuEvent(self, event: QContextMenuEvent) -> None:
            menu = QMenu(self)

            title_action = menu.addAction(self.pet_package.name if self.pet_package else "Antigravity Pet")
            title_action.setEnabled(False)
            menu.addSeparator()

            # Actions submenu
            actions_menu = menu.addMenu("Acciones")
            act_cafe = actions_menu.addAction("☕ Tomar Café")
            act_cafe.triggered.connect(lambda: self.trigger_interaction("cafe"))
            act_saludo = actions_menu.addAction("👋 Saludar")
            act_saludo.triggered.connect(lambda: self.trigger_interaction("saludo"))
            act_quijote = actions_menu.addAction("📖 Leer Don Quijote")
            act_quijote.triggered.connect(lambda: self.trigger_interaction("quijote"))
            act_pizarra = actions_menu.addAction("🧑‍🏫 Explicar en Pizarra")
            act_pizarra.triggered.connect(lambda: self.trigger_interaction("pizarra"))
            act_laptop = actions_menu.addAction("💻 Trabajar / Pensar")
            act_laptop.triggered.connect(lambda: self.trigger_interaction("laptop"))
            act_festejo = actions_menu.addAction("🎉 Festejar Éxito")
            act_festejo.triggered.connect(lambda: self.trigger_interaction("festejo"))
            act_hora = actions_menu.addAction("⏰ Consultar Hora")
            act_hora.triggered.connect(lambda: self.trigger_interaction("hora"))

            menu.addSeparator()

            # Sound toggle
            sound_act = menu.addAction("🔊 Sonidos del Sistema")
            sound_act.setCheckable(True)
            sound_act.setChecked(self.sounds_enabled)
            sound_act.triggered.connect(self.toggle_sounds)

            menu.addSeparator()

            # Pet selection submenu
            pets_menu = menu.addMenu("Pets")
            available = self.loader.list_available_pets()
            for pet_slug in available:
                act = pets_menu.addAction(pet_slug.title())
                act.setCheckable(True)
                if self.pet_package and self.pet_package.slug == pet_slug:
                    act.setChecked(True)
                act.triggered.connect(lambda chk, s=pet_slug: self.load_pet(s))

            # Scale submenu
            scale_menu = menu.addMenu("Scale")
            for sc in [1.0, 1.5, 2.0]:
                act = scale_menu.addAction(f"{sc}x")
                act.setCheckable(True)
                if abs(self.scale_factor - sc) < 0.01:
                    act.setChecked(True)
                act.triggered.connect(lambda chk, s=sc: self.set_scale(s))

            menu.addSeparator()
            reset_act = menu.addAction("Reset Position")
            reset_act.triggered.connect(self.reset_position)

            menu.addSeparator()
            quit_act = menu.addAction("Quit")
            quit_act.triggered.connect(QApplication.instance().quit)

            menu.exec(event.globalPos())

        def reset_position(self) -> None:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.width() - 40, screen.bottom() - self.height() - 40)

        def _on_ipc_event(self, packet: EventPacket) -> None:
            self.event_received_signal.emit(packet)

        def _handle_event_in_main_thread(self, packet: EventPacket) -> None:
            self.interaction_quote = None
            self.interaction_title = None
            if self.interaction_revert_timer.isActive():
                self.interaction_revert_timer.stop()
            self.state_machine.process_event(packet)
            if self.sounds_enabled:
                if packet.event == "Stop" and not packet.error:
                    play_sound_async("chime")
                elif packet.error:
                    play_sound_async("error")

            # After 12s of waiting or review without new agent activity, gracefully return to IDLE with clock
            if packet.event in ("PostInvocation", "PostToolUse", "Stop"):
                self.agent_idle_timer.start(12000)
            else:
                self.agent_idle_timer.stop()

            self.update()

        def closeEvent(self, event) -> None:
            self.ipc_server.stop()
            event.accept()

    app = QApplication(sys.argv)
    loader = AssetLoader()
    available = loader.list_available_pets()
    initial = "cochepa" if "cochepa" in available else ("default" if "default" in available else (available[0] if available else "default"))
    widget = PetOverlayWidget(loader, initial_pet=initial)
    widget.show()
    sys.exit(app.exec())


def main() -> None:
    run_qt_app()


if __name__ == "__main__":
    main()
