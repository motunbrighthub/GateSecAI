"""
crud.py
-------
All database read/write logic lives here, kept separate from the routes
in main.py so main.py stays easy to read.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from . import models, schemas


def create_vehicle(db: Session, vehicle: schemas.VehicleCreate) -> models.Vehicle:
    """Called by the ENTRY gate when a new vehicle arrives."""
    db_vehicle = models.Vehicle(
        plate_number=vehicle.plate_number.strip().upper(),
        vehicle_name=vehicle.vehicle_name.strip(),
        color=vehicle.color,
        owner_name=vehicle.owner_name.strip(),
        phone_number=vehicle.phone_number,
        destination=vehicle.destination,
        photo_filename=vehicle.photo_filename,
        status="IN",
    )
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


def get_active_vehicles(db: Session):
    """Vehicles currently inside (status == IN). This is what the EXIT
    gate screen reads, so it always shows the latest arrivals instantly."""
    return (
        db.query(models.Vehicle)
        .filter(models.Vehicle.status == "IN")
        .order_by(models.Vehicle.time_in.desc())
        .all()
    )


def get_vehicle(db: Session, vehicle_id: int):
    return db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()


def get_active_by_plate_exact(db: Session, plate_number: str):
    """Exact match on an active (status == IN) plate — used to stop the
    same vehicle being registered twice while it's already inside."""
    return (
        db.query(models.Vehicle)
        .filter(
            models.Vehicle.status == "IN",
            models.Vehicle.plate_number == plate_number.strip().upper(),
        )
        .first()
    )


def search_active_by_plate(db: Session, plate_number: str):
    """Used by the exit gate's search box so the guard can quickly find
    a vehicle by typing part of the plate number."""
    q = f"%{plate_number.strip().upper()}%"
    return (
        db.query(models.Vehicle)
        .filter(models.Vehicle.status == "IN", models.Vehicle.plate_number.like(q))
        .order_by(models.Vehicle.time_in.desc())
        .all()
    )


def checkout_vehicle(db: Session, vehicle_id: int):
    """Called by the EXIT gate. Marks the vehicle as gone. Returns None
    if the vehicle doesn't exist or was already checked out."""
    db_vehicle = get_vehicle(db, vehicle_id)
    if db_vehicle and db_vehicle.status == "IN":
        db_vehicle.time_out = datetime.now()
        db_vehicle.status = "OUT"
        db.commit()
        db.refresh(db_vehicle)
        return db_vehicle
    return None


def get_history(db: Session, limit: int = 100):
    """All records (in + out), most recent first — useful for a log/report."""
    return (
        db.query(models.Vehicle)
        .order_by(models.Vehicle.time_in.desc())
        .limit(limit)
        .all()
    )


def get_today_count(db: Session):
    today = datetime.now().date()
    return (
        db.query(models.Vehicle)
        .filter(func.date(models.Vehicle.time_in) == str(today))
        .count()
    )


# ---------- Panic alerts (from GSM SMS listener) ----------

def create_panic_alert(db: Session, sender_number: str, message: str) -> models.PanicAlert:
    alert = models.PanicAlert(sender_number=sender_number, message=message)
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def get_active_panic_alerts(db: Session):
    return (
        db.query(models.PanicAlert)
        .filter(models.PanicAlert.resolved == "NO")
        .order_by(models.PanicAlert.received_at.desc())
        .all()
    )


def resolve_panic_alert(db: Session, alert_id: int):
    alert = db.query(models.PanicAlert).filter(models.PanicAlert.id == alert_id).first()
    if alert:
        alert.resolved = "YES"
        db.commit()
        db.refresh(alert)
    return alert
