"""
main.py
-------
GATEMAN — a paperless visitor/vehicle gate log, now with an optional
computer-vision plate scan at entry.

"""

import os
from fastapi import FastAPI, Request, Depends, Form, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from . import models, schemas, crud, vision
from .database import engine, get_db, SessionLocal
from .gsm_panic import GSMPanicListener

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="GateSecAI")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/captures", StaticFiles(directory=vision.CAPTURES_DIR), name="captures")
templates = Jinja2Templates(directory="templates")

def _handle_panic_alert(sender_number: str, message: str):
    """Called from the GSM background thread whenever a trigger SMS
    arrives. Opens its own short-lived DB session since it isn't
    running inside a normal request."""
    db = SessionLocal()
    try:
        crud.create_panic_alert(db, sender_number, message)
        print(f"[GATEMAN GSM] 🚨 PANIC ALERT from {sender_number}: {message}")
    finally:
        db.close()


_gsm_port = os.getenv("GSM_PORT")
if _gsm_port:
    _gsm_listener = GSMPanicListener(port=_gsm_port, on_alert=_handle_panic_alert)
    _gsm_listener.start()
else:
    print("[GATEMAN GSM] GSM_PORT not set in .env — panic-alert SMS listener is OFF.")


# ---------- PAGE ROUTES ----------

@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    """Dashboard: shows every vehicle currently on the premises."""
    active_vehicles = crud.get_active_vehicles(db)
    today_count = crud.get_today_count(db)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "vehicles": active_vehicles,
            "today_count": today_count,
        },
    )


@app.get("/register")
def register_form(request: Request):
    """Entry gate: show the form to log a new vehicle coming in.
    If a plate was just scanned, it arrives as query params and
    pre-fills the form for the guard to review."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register_submit(
    request: Request,
    plate_number: str = Form(...),
    vehicle_name: str = Form(...),
    color: Optional[str] = Form(None),
    owner_name: str = Form(...),
    phone_number: Optional[str] = Form(None),
    destination: Optional[str] = Form(None),
    photo_filename: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if not plate_number.strip() or not vehicle_name.strip() or not owner_name.strip():
        return RedirectResponse(url="/register?error=blank", status_code=303)

    if crud.get_active_by_plate_exact(db, plate_number):
        return RedirectResponse(url="/register?error=duplicate", status_code=303)

    vehicle_in = schemas.VehicleCreate(
        plate_number=plate_number,
        vehicle_name=vehicle_name,
        color=color,
        owner_name=owner_name,
        phone_number=phone_number,
        destination=destination,
        photo_filename=photo_filename,
    )
    crud.create_vehicle(db, vehicle_in)
    return RedirectResponse(url="/register?success=1", status_code=303)


@app.get("/scan")
def scan_page(request: Request):
    """Camera capture page — opens the phone/device camera, uploads the
    photo, and shows the OCR result for the guard to confirm/edit
    before it's saved as a registration."""
    return templates.TemplateResponse("scan.html", {"request": request})


@app.post("/api/scan-plate")
async def scan_plate(photo: UploadFile = File(...)):
    """Runs offline OCR on an uploaded photo and returns the detected
    plate number + confidence + where the photo was saved. Does NOT
    save a vehicle record — that only happens when the guard confirms
    via the normal /register submission."""
    image_bytes = await photo.read()
    plate_text, confidence, photo_filename = vision.read_plate_from_bytes(image_bytes)
    return JSONResponse({
        "plate_number": plate_text,
        "confidence": round(confidence, 3),
        "photo_filename": photo_filename,
    })


@app.get("/checkout")
def checkout_page(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    """Exit gate: list of vehicles still inside, with a search box and a
    'Check Out' button next to each one."""
    if q:
        vehicles = crud.search_active_by_plate(db, q)
    else:
        vehicles = crud.get_active_vehicles(db)
    return templates.TemplateResponse(
        "checkout.html",
        {"request": request, "vehicles": vehicles, "query": q or ""},
    )


@app.post("/checkout/{vehicle_id}")
def checkout_submit(vehicle_id: int, db: Session = Depends(get_db)):
    result = crud.checkout_vehicle(db, vehicle_id)
    if result is None:
        return RedirectResponse(url="/checkout?error=notfound", status_code=303)
    return RedirectResponse(url="/checkout?success=1", status_code=303)


# ---------- JSON API (used by script.js for live auto-refresh) ----------

@app.get("/api/active", response_model=list[schemas.VehicleOut])
def api_active_vehicles(db: Session = Depends(get_db)):
    """Polled every few seconds by index.html and checkout.html so both
    gate screens stay in sync without a manual page reload."""
    return crud.get_active_vehicles(db)


@app.get("/api/history", response_model=list[schemas.VehicleOut])
def api_history(limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_history(db, limit)


# ---------- PANIC ALERTS ----------

@app.get("/panic-alerts")
def panic_alerts_page(request: Request, db: Session = Depends(get_db)):
    alerts = crud.get_active_panic_alerts(db)
    return templates.TemplateResponse("panic_alerts.html", {"request": request, "alerts": alerts})


@app.post("/panic-alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    crud.resolve_panic_alert(db, alert_id)
    return RedirectResponse(url="/panic-alerts?success=1", status_code=303)


@app.get("/api/panic-alerts/active")
def api_active_panic_alerts(db: Session = Depends(get_db)):
    alerts = crud.get_active_panic_alerts(db)
    return [
        {"id": a.id, "sender_number": a.sender_number, "message": a.message,
         "received_at": a.received_at.isoformat()}
        for a in alerts
    ]


@app.post("/panic-alerts/simulate")
def simulate_panic_alert(
    sender_number: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
):
    """Creates a panic alert exactly the way the real GSM hardware would —
    used for demos/testing when a physical SIM800L module isn't available.
    This calls the SAME crud.create_panic_alert function the GSM listener
    calls, so the dashboard banner behaves identically either way."""
    crud.create_panic_alert(db, sender_number, message)
    return RedirectResponse(url="/?success=simulated", status_code=303)
