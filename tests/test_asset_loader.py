"""Unit tests for Codex AssetLoader and pet package parsing."""

import json
from pathlib import Path
import tempfile
import unittest

from core.asset_loader import (
    DEFAULT_CELL_HEIGHT,
    DEFAULT_CELL_WIDTH,
    DEFAULT_COLUMNS,
    DEFAULT_ROWS_V1,
    AssetLoader,
)
from core.state_machine import PetState


class TestAssetLoader(unittest.TestCase):
    """Test asset resolution, pet.json parsing, and fallback behaviors."""

    def setUp(self) -> None:
        self.loader = AssetLoader()

    def test_discover_default_pet(self) -> None:
        pets = self.loader.list_available_pets()
        self.assertIn("default", pets)

    def test_load_default_pet_package(self) -> None:
        pet = self.loader.load_pet("default")
        self.assertEqual(pet.slug, "default")
        self.assertEqual(pet.name, "Antigravity Pet")
        self.assertEqual(pet.columns, 8)
        self.assertEqual(pet.rows, 9)
        self.assertEqual(pet.cell_width, 192)
        self.assertEqual(pet.cell_height, 208)
        self.assertTrue(pet.spritesheet_path.exists())

    def test_frame_rect_calculations(self) -> None:
        pet = self.loader.load_pet("default")

        # Row 0 (Idle), Frame 0
        rect0 = pet.get_frame_rect(PetState.IDLE, 0)
        self.assertEqual(rect0, (0, 0, 192, 208))

        # Row 0 (Idle), Frame 3
        rect3 = pet.get_frame_rect(PetState.IDLE, 3)
        self.assertEqual(rect3, (3 * 192, 0, 192, 208))

        # Row 7 (Working), Frame 2
        rect_work = pet.get_frame_rect(PetState.WORKING, 2)
        self.assertEqual(rect_work, (2 * 192, 7 * 208, 192, 208))

        # Row 5 (Failed), Frame 7
        rect_fail = pet.get_frame_rect(PetState.FAILED, 7)
        self.assertEqual(rect_fail, (7 * 192, 5 * 208, 192, 208))

    def test_nonexistent_pet_raises_filenotfound(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.loader.load_pet("nonexistent_pet_slug_12345")

    def test_corrupt_pet_json_graceful_fallback(self) -> None:
        """Verify that corrupted pet.json falls back to default grid without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pet_dir = Path(tmpdir) / "corrupt_pet"
            pet_dir.mkdir()

            # Corrupt pet.json
            with open(pet_dir / "pet.json", "w") as f:
                f.write("{ invalid json content ...")

            # Fake spritesheet
            with open(pet_dir / "spritesheet.png", "wb") as f:
                f.write(b"PNGFAKE")

            loader = AssetLoader(search_paths=[Path(tmpdir)])
            pet = loader.load_pet("corrupt_pet")

            self.assertEqual(pet.slug, "corrupt_pet")
            self.assertEqual(pet.columns, DEFAULT_COLUMNS)
            self.assertEqual(pet.rows, DEFAULT_ROWS_V1)
            self.assertEqual(pet.cell_width, DEFAULT_CELL_WIDTH)
            self.assertEqual(pet.cell_height, DEFAULT_CELL_HEIGHT)


if __name__ == "__main__":
    unittest.main()
