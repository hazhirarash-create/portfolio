from database import Base
from sqlalchemy import Column, ForeignKey, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

class BaseORMModel(Base):

    __abstract__ = True

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        nullable=False
                        )
    updated_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc),
                        nullable=False
                        )