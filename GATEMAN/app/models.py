"""
models.py
---------
One table: `vehicles`. Every row is one visit (one entry -> one exit).

status is either:
  "IN"  -> vehicle is currently on the premises (checked in, not yet out)
  "OUT" -> vehicle has left (time_out has been recorded)

time_in/time_out both come from Python's clock (not the database
server's), so they can never drift apart due to a timezone mismatch
between the app server and the database server.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from .database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)

    plate_number = Column(String(20), index=True, nullable=False)
    vehicle_name = Column(String(100), nullable=False)     # e.g. "Toyota Camry"
    color = Column(String(50), nullable=True)
    owner_name = Column(String(100), nullable=False)
    phone_number = Column(String(30), nullable=True)
    destination = Column(String(150), nullable=True)        # who/where they're visiting
    photo_filename = Column(String(255), nullable=True)      # captured entry photo, if any

    time_in = Column(DateTime, default=datetime.now)
    time_out = Column(DateTime, nullable=True)

    status = Column(String(10), default="IN")               # "IN" or "OUT"


class PanicAlert(Base):
    __tablename__ = "panic_alerts"

    id = Column(Integer, primary_key=True, index=True)
    sender_number = Column(String(30), nullable=False)
    message = Column(String(300), nullable=False)
    received_at = Column(DateTime, default=datetime.now)
    resolved = Column(String(10), default="NO")   # "NO" or "YES" — kept as a
                                                     # string for the same
                                                     # simple pattern as `status`
