"""Stable compatibility entrypoint for the durable local API."""

from .memory_api import create_app, default_database_path


app = create_app()


__all__ = ["app", "create_app", "default_database_path"]
