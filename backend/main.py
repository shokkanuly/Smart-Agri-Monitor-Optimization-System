from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from pydantic import BaseModel

import database
import models
import auth
import prediction_engine

# Initialize database tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Smart Agri-Monitor & Optimization API")

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, lock this down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Schemas ---

class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class FarmCreate(BaseModel):
    name: str
    location: Optional[str] = "Izmir, Turkey"

class FarmResponse(BaseModel):
    id: int
    name: str
    location: str
    user_id: int
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class DeviceCreate(BaseModel):
    name: str
    farm_id: int

class DeviceResponse(BaseModel):
    id: int
    name: str
    api_key: str
    farm_id: int
    status: str
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class TelemetryCreate(BaseModel):
    soil_moisture: float
    ph: float
    temperature: float
    humidity: float

class TelemetryResponse(BaseModel):
    id: int
    device_id: int
    timestamp: datetime.datetime
    soil_moisture: float
    ph: float
    temperature: float
    humidity: float
    is_anomaly: bool
    class Config:
        from_attributes = True

class WateringLogCreate(BaseModel):
    device_id: int
    duration_seconds: int
    manual_override: bool = False

class WateringLogResponse(BaseModel):
    id: int
    device_id: int
    timestamp: datetime.datetime
    duration_seconds: int
    status: str
    manual_override: bool
    class Config:
        from_attributes = True

class PredictionResponse(BaseModel):
    device_id: int
    current_soil_moisture: float
    temperature: float
    humidity: float
    ph: float
    weather_precipitation_probability: float
    weather_cloud_cover: float
    recommended_duration_seconds: float
    model_used: str # "random_forest_ml" or "procedural_math"
    timestamp: datetime.datetime

# --- Auth Endpoints ---

@app.post("/api/auth/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_pwd = auth.get_password_hash(user_data.password)
    new_user = models.User(username=user_data.username, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/auth/login", response_model=Token)
def login(user_data: UserCreate, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if not user or not auth.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

# --- Farm Endpoints ---

@app.post("/api/farms", response_model=FarmResponse)
def create_farm(farm_data: FarmCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    new_farm = models.Farm(name=farm_data.name, location=farm_data.location, user_id=current_user.id)
    db.add(new_farm)
    db.commit()
    db.refresh(new_farm)
    return new_farm

@app.get("/api/farms", response_model=List[FarmResponse])
def list_farms(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    return db.query(models.Farm).filter(models.Farm.user_id == current_user.id).all()

# --- Device Endpoints ---

@app.post("/api/devices", response_model=DeviceResponse)
def create_device(device_data: DeviceCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    # Verify farm belongs to current user
    farm = db.query(models.Farm).filter(models.Farm.id == device_data.farm_id, models.Farm.user_id == current_user.id).first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found or unauthorized")
        
    # Generate unique api_key (e.g. node-xxxx)
    import uuid
    api_key = f"node-{uuid.uuid4().hex[:12]}"
    
    new_device = models.Device(name=device_data.name, api_key=api_key, farm_id=device_data.farm_id)
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device

@app.get("/api/devices", response_model=List[DeviceResponse])
def list_devices(farm_id: Optional[int] = None, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    query = db.query(models.Device).join(models.Farm).filter(models.Farm.user_id == current_user.id)
    if farm_id:
        query = query.filter(models.Device.farm_id == farm_id)
    return query.all()

# --- Telemetry Ingestion Endpoints (Used by ESP32 / Simulator) ---

@app.post("/api/telemetry", response_model=TelemetryResponse)
def ingest_telemetry(
    data: TelemetryCreate,
    x_api_key: str = Header(..., description="Device authentication API Key"),
    db: Session = Depends(database.get_db)
):
    device = db.query(models.Device).filter(models.Device.api_key == x_api_key).first()
    if not device:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    # Edge anomaly detection check (simple threshold checks simulating edge filters)
    # E.g. Soil moisture dropping below 15% (extreme dryness) or temp above 45C
    is_anomaly = False
    if data.soil_moisture < 15.0 or data.temperature > 45.0 or data.ph < 4.5 or data.ph > 8.5:
        is_anomaly = True
        
    new_telemetry = models.Telemetry(
        device_id=device.id,
        soil_moisture=data.soil_moisture,
        ph=data.ph,
        temperature=data.temperature,
        humidity=data.humidity,
        is_anomaly=is_anomaly
    )
    db.add(new_telemetry)
    db.commit()
    db.refresh(new_telemetry)
    return new_telemetry

@app.get("/api/telemetry", response_model=List[TelemetryResponse])
def query_telemetry(
    device_id: int,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify ownership of device
    device = db.query(models.Device).join(models.Farm).filter(
        models.Device.id == device_id,
        models.Farm.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
        
    # Query time-series telemetry
    readings = db.query(models.Telemetry).filter(
        models.Telemetry.device_id == device_id
    ).order_by(models.Telemetry.timestamp.desc()).limit(limit).all()
    
    # Return in chronological order
    readings.reverse()
    return readings

# --- Watering Log Endpoints ---

@app.post("/api/watering", response_model=WateringLogResponse)
def log_watering(
    log_data: WateringLogCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify ownership of device
    device = db.query(models.Device).join(models.Farm).filter(
        models.Device.id == log_data.device_id,
        models.Farm.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
        
    new_log = models.WateringLog(
        device_id=log_data.device_id,
        duration_seconds=log_data.duration_seconds,
        manual_override=log_data.manual_override,
        status="completed"
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log

@app.get("/api/watering/logs", response_model=List[WateringLogResponse])
def get_watering_logs(
    device_id: int,
    limit: int = 50,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify ownership of device
    device = db.query(models.Device).join(models.Farm).filter(
        models.Device.id == device_id,
        models.Farm.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
        
    return db.query(models.WateringLog).filter(
        models.WateringLog.device_id == device_id
    ).order_by(models.WateringLog.timestamp.desc()).limit(limit).all()

# --- Weather & Optimization Endpoints ---

@app.get("/api/weather")
def get_weather_forecast(lat: float = 38.4189, lon: float = 27.1287):
    """
    Returns simulated weather forecast for Turkey (defaults to Izmir region: 38.4189° N, 27.1287° E).
    Changes forecast conditions based on current hours to simulate real environmental changes.
    """
    now = datetime.datetime.utcnow()
    hour = now.hour
    
    # Generate variations based on hours (diurnal cycle)
    # We will simulate: temperature range 18-35C, humidity 30-85%
    base_temp = 25.0
    temp_variation = 7.0 * math_sine_helper(hour)
    temp = round(base_temp + temp_variation, 1)
    
    humidity = round(60.0 - 20.0 * math_sine_helper(hour), 1)
    
    # Simulate a cloud/rain cycle (changes every few days or hours)
    day_cycle = (now.day + now.hour // 6) % 3
    if day_cycle == 0:
        precip_prob = 75.0
        cloud_cover = 90.0
        condition = "Rain Expected"
        temp -= 4.0 # cooler when rainy
    elif day_cycle == 1:
        precip_prob = 15.0
        cloud_cover = 40.0
        condition = "Partly Cloudy"
    else:
        precip_prob = 0.0
        cloud_cover = 10.0
        condition = "Sunny"
        
    return {
        "location": "Izmir, Turkey",
        "latitude": lat,
        "longitude": lon,
        "temperature": temp,
        "humidity": humidity,
        "precipitation_probability": precip_prob,
        "cloud_cover": cloud_cover,
        "condition": condition,
        "timestamp": now
    }

def math_sine_helper(hour: int) -> float:
    import math
    # Map 0-23 hours to a sine curve peaking at 14:00 (hour 14)
    return math.sin((hour - 8) * math.pi / 12)

@app.get("/api/predictions/schedule", response_model=PredictionResponse)
def get_prediction_schedule(
    device_id: int,
    mode: str = "ml", # "ml" or "math"
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify ownership of device
    device = db.query(models.Device).join(models.Farm).filter(
        models.Device.id == device_id,
        models.Farm.user_id == current_user.id
    ).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found or unauthorized")
        
    # Get latest telemetry
    latest_telemetry = db.query(models.Telemetry).filter(
        models.Telemetry.device_id == device_id
    ).order_by(models.Telemetry.timestamp.desc()).first()
    
    # Default fallback values if no telemetry exists yet
    moisture = 40.0
    temp = 25.0
    humidity = 50.0
    ph = 6.5
    
    if latest_telemetry:
        moisture = latest_telemetry.soil_moisture
        temp = latest_telemetry.temperature
        humidity = latest_telemetry.humidity
        ph = latest_telemetry.ph
        
    # Get weather forecast
    weather = get_weather_forecast()
    precip_prob = weather["precipitation_probability"]
    cloud_cover = weather["cloud_cover"]
    
    # Calculate recommended duration based on mode
    if mode == "math":
        rec_duration = prediction_engine.procedural_watering_estimate(
            current_moisture=moisture,
            temp=temp,
            humidity=humidity
        )
        # Apply rain reduction factor
        if precip_prob > 70.0:
            rec_duration *= 0.1
        elif precip_prob > 40.0:
            rec_duration *= 0.5
        model_used = "procedural_math"
    else:
        rec_duration = prediction_engine.predict_watering_duration(
            current_moisture=moisture,
            temperature=temp,
            humidity=humidity,
            ph=ph,
            precip_prob=precip_prob,
            cloud_cover=cloud_cover
        )
        model_used = "random_forest_ml"
        
    return {
        "device_id": device_id,
        "current_soil_moisture": moisture,
        "temperature": temp,
        "humidity": humidity,
        "ph": ph,
        "weather_precipitation_probability": precip_prob,
        "weather_cloud_cover": cloud_cover,
        "recommended_duration_seconds": round(rec_duration, 1),
        "model_used": model_used,
        "timestamp": datetime.datetime.utcnow()
    }

@app.post("/api/predictions/train")
def trigger_training(current_user: models.User = Depends(auth.get_current_user)):
    try:
        prediction_engine.train_predictive_model()
        return {"status": "success", "message": "Model trained successfully on generated crop metrics."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")
