"""Backend module for AI-Assisted Movie Maker."""

from .db import Database
from .assets import AssetManager
from .ai import AIOperations

__all__ = ["Database", "AssetManager", "AIOperations"]
