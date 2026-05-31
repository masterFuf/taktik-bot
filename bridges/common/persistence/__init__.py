"""Persistence facades shared by bridge entrypoints."""

from .database import SentDMService, get_db_path, get_repository

__all__ = ["SentDMService", "get_db_path", "get_repository"]
