"""Modular domain features for Antigravity Pets companion.

Provides:
- PomodoroManager: 25m work / 5m break cycle with active health recommendations.
- ActionHistory: Ring buffer tracking recent agent actions.
- GitMonitor: Non-blocking inspector for active branch and dirty status.
- PhysicsEngine: Realistic gravity and bounce damping for desktop overlay drops.
- WatchdogTimer: Detection of hung or prolonged commands (>120s).
- ArchitectureWisdom: Catalog of Senior Architect advice, SOLID, and Clean Architecture principles.
"""

from collections import deque
from datetime import datetime
import os
import random
import subprocess
import threading
import time
from typing import Callable, Deque, Dict, List, NamedTuple, Optional, Tuple


class ActionRecord(NamedTuple):
    """Immutable record of an agent lifecycle event for the history drawer."""
    timestamp: float
    time_str: str
    event: str
    tool: Optional[str]
    title: str
    detail: str
    is_error: bool
    is_secret: bool


class ActionHistory:
    """Thread-safe ring buffer keeping the last N agent actions."""

    def __init__(self, max_entries: int = 10) -> None:
        self.max_entries = max_entries
        self._history: Deque[ActionRecord] = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def add(
        self,
        event: str,
        tool: Optional[str],
        title: str,
        detail: str,
        is_error: bool = False,
        is_secret: bool = False,
    ) -> ActionRecord:
        now = time.time()
        time_str = datetime.fromtimestamp(now).strftime("%H:%M:%S")
        record = ActionRecord(
            timestamp=now,
            time_str=time_str,
            event=event,
            tool=tool,
            title=title,
            detail=detail,
            is_error=is_error,
            is_secret=is_secret,
        )
        with self._lock:
            self._history.append(record)
        return record

    def get_recent(self, count: int = 5) -> List[ActionRecord]:
        with self._lock:
            items = list(self._history)
        return list(reversed(items[-count:]))

    def clear(self) -> None:
        with self._lock:
            self._history.clear()


class WatchdogTimer:
    """Monitors running tasks to detect prolonged or hung commands (>120s)."""

    def __init__(
        self,
        timeout_seconds: float = 120.0,
        on_timeout: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.on_timeout = on_timeout
        self._start_time: Optional[float] = None
        self._active_task_name: Optional[str] = None
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()

    def task_started(self, task_name: str) -> None:
        """Called when a tool execution or thinking phase starts."""
        with self._lock:
            self.task_completed()  # Cancel any existing timer
            self._active_task_name = task_name
            self._start_time = time.time()
            self._timer = threading.Timer(self.timeout_seconds, self._handle_timeout)
            self._timer.daemon = True
            self._timer.start()

    def task_completed(self) -> None:
        """Called when a tool finishes or agent pauses."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._start_time = None
            self._active_task_name = None

    def _handle_timeout(self) -> None:
        with self._lock:
            task = self._active_task_name or "Tarea en ejecución"
            elapsed = time.time() - (self._start_time or time.time())
        if self.on_timeout:
            try:
                self.on_timeout(task, elapsed)
            except Exception:
                pass


class GitStatus(NamedTuple):
    branch: str
    is_dirty: bool
    is_protected: bool  # main, master, production, release


class GitMonitor:
    """Inspects git repository status without blocking the UI thread."""

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = repo_path
        self._cached_status: GitStatus = GitStatus(branch="main", is_dirty=False, is_protected=True)
        self._lock = threading.Lock()

    def refresh(self) -> GitStatus:
        """Query git CLI for active branch and uncommitted modifications."""
        try:
            # Get current branch
            res_branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "unknown"

            # Check for dirty changes
            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            is_dirty = bool(res_status.stdout.strip()) if res_status.returncode == 0 else False
            is_protected = branch in ("main", "master", "prod", "production", "release")

            status = GitStatus(branch=branch, is_dirty=is_dirty, is_protected=is_protected)
            with self._lock:
                self._cached_status = status
            return status
        except Exception:
            with self._lock:
                return self._cached_status

    @property
    def current(self) -> GitStatus:
        with self._lock:
            return self._cached_status


class PomodoroManager:
    """Manages 25m work / 5m active break cycles with health recommendations."""

    WORK_DURATION = 25 * 60  # 25 minutes
    BREAK_DURATION = 5 * 60  # 5 minutes

    ACTIVE_BREAK_TIPS = [
        "👀 Regla 20-20-20: Mirá un punto a 6 metros durante 20 segundos para descansar la vista.",
        "💧 Momento de hidratación: Tomá un buen vaso de agua fresca.",
        "🧘 Postura y hombros: Estirá el cuello suavemente y rotá los hombros hacia atrás.",
        "🚶 Caminata breve: Levantate de la silla y caminá un minuto para activar la circulación.",
        "🫁 Respiración consciente: Hacé tres respiraciones lentas y profundas.",
    ]

    def __init__(
        self,
        on_break_start: Optional[Callable[[str], None]] = None,
        on_work_start: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_break_start = on_break_start
        self.on_work_start = on_work_start
        self.is_running = False
        self.is_break = False
        self.seconds_left = self.WORK_DURATION
        self.completed_cycles = 0

    def start(self) -> None:
        self.is_running = True
        self.is_break = False
        self.seconds_left = self.WORK_DURATION

    def pause(self) -> None:
        self.is_running = False

    def resume(self) -> None:
        self.is_running = True

    def reset(self) -> None:
        self.is_running = False
        self.is_break = False
        self.seconds_left = self.WORK_DURATION

    def tick_second(self) -> Optional[str]:
        """Call every second. Returns tip when entering break, or None."""
        if not self.is_running:
            return None

        self.seconds_left -= 1
        if self.seconds_left <= 0:
            if not self.is_break:
                # Transition to break
                self.is_break = True
                self.seconds_left = self.BREAK_DURATION
                self.completed_cycles += 1
                tip = random.choice(self.ACTIVE_BREAK_TIPS)
                if self.on_break_start:
                    self.on_break_start(tip)
                return tip
            else:
                # Transition back to work
                self.is_break = False
                self.seconds_left = self.WORK_DURATION
                if self.on_work_start:
                    self.on_work_start()
                return None
        return None

    @property
    def formatted_time(self) -> str:
        mins = max(0, self.seconds_left) // 60
        secs = max(0, self.seconds_left) % 60
        return f"{mins:02d}:{secs:02d}"


class PhysicsEngine:
    """Calculates gravitational drop and bounce damping for desktop window release."""

    def __init__(self, gravity: float = 2.8, elasticity: float = 0.35) -> None:
        self.gravity = gravity
        self.elasticity = elasticity
        self.velocity_y = 0.0
        self.is_active = False

    def start_drop(self, initial_velocity: float = 0.0) -> None:
        self.velocity_y = initial_velocity
        self.is_active = True

    def update_position(self, current_y: int, floor_y: int) -> Tuple[int, bool]:
        """Returns (new_y, has_settled)."""
        if not self.is_active:
            return current_y, True

        self.velocity_y += self.gravity
        new_y = current_y + self.velocity_y

        if new_y >= floor_y:
            new_y = floor_y
            self.velocity_y = -self.velocity_y * self.elasticity
            # Settle threshold
            if abs(self.velocity_y) < 1.2:
                self.velocity_y = 0.0
                self.is_active = False
                return floor_y, True

        return int(new_y), False


class ArchitectureWisdom:
    """Collection of Senior Architect advice, SOLID principles, and Clean Code pearls."""

    PILLS = [
        "«SOLID: El Principio de Responsabilidad Única (SRP) no es hacer clases chicas, es que una clase tenga una sola razón para cambiar.»",
        "«Arquitectura Hexagonal: Tu lógica de dominio jamás debe importar frameworks, librerías de UI o drivers de base de datos.»",
        "«Concepts > Code: Si no podés explicar la arquitectura con una caja y tres flechas, todavía no la entendiste.»",
        "«Against Immediacy: El código más rápido de escribir suele ser el más caro de mantener. Tómense el tiempo de diseñar.»",
        "«Clean Code: Los nombres deben revelar la intención. Si un comentario explica QUÉ hace el código, el nombre está mal puesto.»",
        "«YAGNI: 'You Aren't Gonna Need It'. No agregues abstracciones ni capas de indirección para problemas hipotéticos del futuro.»",
        "«DRY: Don't Repeat Yourself no es duplicación de líneas, es duplicación de conocimiento. Dos cosas parecidas pueden cambiar por razones distintas.»",
        "«Testing: Los tests unitarios deben testear comportamiento público, no implementación interna. Si refactorizás y se rompen, testeaste mal.»",
        "«Inversión de Dependencias (DIP): Los módulos de alto nivel no deben depender de los de bajo nivel; ambos deben depender de abstracciones.»",
        "«Inmutabilidad: Si un objeto no puede cambiar su estado después de nacer, eliminás de raíz el 80% de los bugs de concurrencia.»",
        "«Container-Presentational: Separá los componentes que traen datos de los componentes que solo renderizan píxeles puros.»",
        "«Evitá el 'God Object': Si una clase maneja la red, la base de datos y la UI, estás construyendo un monolito imposible de testear.»",
    ]

    @classmethod
    def get_random_pill(cls) -> str:
        return random.choice(cls.PILLS)
