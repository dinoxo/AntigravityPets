"""Codex-compatible asset loader for Antigravity Pets."""

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.state_machine import PetState, STATE_TO_ROW

logger = logging.getLogger("AntigravityPets.AssetLoader")

DEFAULT_CELL_WIDTH = 192
DEFAULT_CELL_HEIGHT = 208
DEFAULT_COLUMNS = 8
DEFAULT_ROWS_V1 = 9
DEFAULT_ROWS_V2 = 11
DEFAULT_FPS = 10


@dataclass
class AnimationMeta:
    """Metadata for an individual state animation."""

    row: int
    frames: int = 8
    fps: int = DEFAULT_FPS


@dataclass
class PetPackage:
    """Complete loaded Codex pet package."""

    slug: str
    name: str
    version: str
    path: Path
    spritesheet_path: Path
    columns: int = DEFAULT_COLUMNS
    rows: int = DEFAULT_ROWS_V1
    cell_width: int = DEFAULT_CELL_WIDTH
    cell_height: int = DEFAULT_CELL_HEIGHT
    default_fps: int = DEFAULT_FPS
    animations: Dict[PetState, AnimationMeta] = field(default_factory=dict)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def get_frame_rect(self, state: PetState, frame_index: int) -> Tuple[int, int, int, int]:
        """Calculate pixel rectangle (x, y, width, height) on the spritesheet."""
        anim = self.animations.get(state)
        row = anim.row if anim else STATE_TO_ROW.get(state, 0)
        max_frames = anim.frames if anim else self.columns
        col = frame_index % max(1, max_frames)

        x = col * self.cell_width
        y = row * self.cell_height
        return (x, y, self.cell_width, self.cell_height)


class AssetLoader:
    """Locates and loads Codex v1 and v2 pet assets across search directories."""

    def __init__(self, search_paths: Optional[List[Path]] = None) -> None:
        if search_paths is not None:
            self.search_paths = search_paths
        else:
            base_dir = Path(__file__).resolve().parent.parent
            self.search_paths = [
                Path(os.path.expanduser("~/.antigravity/pets")),
                Path(os.path.expanduser("~/.codex/pets")),
                base_dir / "assets" / "pets",
            ]

    def list_available_pets(self) -> List[str]:
        """Return list of distinct pet slugs found across all search paths."""
        found = set()
        for root in self.search_paths:
            if not root.is_dir():
                continue
            for item in root.iterdir():
                if item.is_dir():
                    # Check if it contains pet.json or spritesheet
                    if (item / "pet.json").exists() or any(item.glob("spritesheet.*")):
                        found.add(item.name)
        return sorted(found)

    def resolve_pet_path(self, slug: str) -> Optional[Path]:
        """Find the directory for a given pet slug in prioritized search paths."""
        for root in self.search_paths:
            candidate = root / slug
            if candidate.is_dir():
                return candidate
        return None

    def load_pet(self, slug_or_path: str) -> PetPackage:
        """Load a pet package by slug or direct directory path.

        Raises FileNotFoundError if the pet cannot be resolved.
        """
        p = Path(slug_or_path)
        if p.is_dir():
            pet_dir = p
            slug = pet_dir.name
        else:
            slug = slug_or_path
            resolved = self.resolve_pet_path(slug)
            if not resolved:
                raise FileNotFoundError(f"Pet '{slug}' not found in search paths: {self.search_paths}")
            pet_dir = resolved

        pet_json_path = pet_dir / "pet.json"
        metadata: Dict[str, Any] = {}
        if pet_json_path.is_file():
            try:
                with open(pet_json_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.warning("Failed parsing %s: %s. Using default metadata.", pet_json_path, e)

        name = metadata.get("displayName") or metadata.get("name") or slug.replace("-", " ").replace("_", " ").title()
        version_num = metadata.get("spriteVersionNumber", 1)
        version = str(metadata.get("version", f"{version_num}.0.0"))

        grid_meta = metadata.get("grid", {})
        columns = int(grid_meta.get("columns", DEFAULT_COLUMNS))
        default_rows = DEFAULT_ROWS_V2 if version_num == 2 else DEFAULT_ROWS_V1
        rows = int(grid_meta.get("rows", default_rows))
        cell_width = int(grid_meta.get("cell_width", DEFAULT_CELL_WIDTH))
        cell_height = int(grid_meta.get("cell_height", DEFAULT_CELL_HEIGHT))
        default_fps = int(metadata.get("fps", DEFAULT_FPS))

        # Find spritesheet (webp, png, etc.)
        spritesheet_path = None
        explicit_path = metadata.get("spritesheetPath")
        if explicit_path:
            candidate = pet_dir / explicit_path
            if candidate.is_file():
                spritesheet_path = candidate

        if not spritesheet_path:
            for ext in [".webp", ".png", ".jpg", ".jpeg"]:
                candidate = pet_dir / f"spritesheet{ext}"
                if candidate.is_file():
                    spritesheet_path = candidate
                    break

        if not spritesheet_path:
            # Check any image file in directory
            for ext in ["*.webp", "*.png", "*.jpg"]:
                matches = list(pet_dir.glob(ext))
                if matches:
                    spritesheet_path = matches[0]
                    break

        if not spritesheet_path:
            raise FileNotFoundError(f"No spritesheet found in '{pet_dir}'")

        # Parse animation row overrides if specified in pet.json
        raw_anims = metadata.get("animations", {})
        animations: Dict[PetState, AnimationMeta] = {}

        for state in PetState:
            key = state.value
            if key in raw_anims:
                a_meta = raw_anims[key]
                animations[state] = AnimationMeta(
                    row=int(a_meta.get("row", STATE_TO_ROW[state])),
                    frames=int(a_meta.get("frames", columns)),
                    fps=int(a_meta.get("fps", default_fps)),
                )
            else:
                animations[state] = AnimationMeta(
                    row=STATE_TO_ROW[state],
                    frames=columns,
                    fps=default_fps,
                )

        return PetPackage(
            slug=slug,
            name=name,
            version=version,
            path=pet_dir,
            spritesheet_path=spritesheet_path,
            columns=columns,
            rows=rows,
            cell_width=cell_width,
            cell_height=cell_height,
            default_fps=default_fps,
            animations=animations,
            raw_metadata=metadata,
        )
