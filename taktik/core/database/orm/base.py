"""ORM pilot (Vague D) - shared SQLAlchemy declarative base.

One Base/metadata shared by all piloted entities. The metadata is used only for
MAPPING existing tables - never for DDL on the shared dual-runtime base.
"""
from __future__ import annotations

from sqlalchemy.orm import declarative_base

Base = declarative_base()
