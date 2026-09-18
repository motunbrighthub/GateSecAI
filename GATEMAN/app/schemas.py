from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class VehicleCreate(BaseModel):
    plate_number: str
    vehicle_name: str
    color: Optional[str] = None
    owner_name: str
    phone_number: Optional[str] = None
    destination: Optional[str] = None
    photo_filename: Optional[str] = None


class VehicleOut(BaseModel):
    id: int
    plate_number: str
    vehicle_name: str
    color: Optional[str] = None
    owner_name: str
    phone_number: Optional[str] = None
    destination: Optional[str] = None
    photo_filename: Optional[str] = None
    time_in: datetime
    time_out: Optional[datetime] = None
    status: str

    class Config:
        from_attributes = True  

class ScanResult(BaseModel):
    plate_number: str
    confidence: float
    photo_filename: str
