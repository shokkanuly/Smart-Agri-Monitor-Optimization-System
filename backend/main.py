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
import os
import requests

# Load environment variables from .env if it exists
if os.path.exists(".env"):
    try:
        with open(".env") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    parts = line.strip().split("=", 1)
                    if len(parts) == 2:
                        os.environ[parts[0].strip()] = parts[1].strip()
    except Exception:
        pass

TOMORROW_API_KEY = os.environ.get("TOMORROW_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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
    Returns weather forecast for Turkey (defaults to Izmir region: 38.4189° N, 27.1287° E)
    fetched in real time from Tomorrow.io. Falls back to simulated weather if Tomorrow.io is down/rate-limited.
    """
    now = datetime.datetime.utcnow()
    
    # Try calling Tomorrow.io
    if TOMORROW_API_KEY:
        try:
            url = f"https://api.tomorrow.io/v4/weather/realtime?location={lat},{lon}&apikey={TOMORROW_API_KEY}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                values = data.get("data", {}).get("values", {})
                
                # Weather code map
                weather_code = values.get("weatherCode", 1000)
                weather_codes_map = {
                    1000: "Sunny",
                    1100: "Mostly Clear",
                    1101: "Partly Cloudy",
                    1102: "Mostly Cloudy",
                    1001: "Cloudy",
                    2000: "Fog",
                    2100: "Light Fog",
                    4000: "Drizzle",
                    4001: "Rain Expected",
                    4200: "Light Rain",
                    4201: "Heavy Rain",
                    5000: "Snow",
                    5001: "Flurries",
                    5100: "Light Snow",
                    5101: "Heavy Snow",
                    6000: "Freezing Drizzle",
                    6001: "Freezing Rain",
                    6200: "Light Freezing Rain",
                    6201: "Heavy Freezing Rain",
                    7000: "Ice Pellets",
                    7101: "Heavy Ice Pellets",
                    7102: "Light Ice Pellets",
                    8000: "Thunderstorm"
                }
                condition = weather_codes_map.get(weather_code, "Sunny")
                
                return {
                    "location": "Izmir, Turkey",
                    "latitude": lat,
                    "longitude": lon,
                    "temperature": round(values.get("temperature", 25.0), 1),
                    "humidity": round(values.get("humidity", 50.0), 1),
                    "precipitation_probability": float(values.get("precipitationProbability", 0.0)),
                    "cloud_cover": float(values.get("cloudCover", 0.0)),
                    "condition": condition,
                    "timestamp": now
                }
        except Exception:
            pass  # Fallback to simulated logic below

    # --- Fallback Simulated Weather ---
    hour = now.hour
    base_temp = 25.0
    temp_variation = 7.0 * math_sine_helper(hour)
    temp = round(base_temp + temp_variation, 1)
    humidity = round(60.0 - 20.0 * math_sine_helper(hour), 1)
    
    day_cycle = (now.day + now.hour // 6) % 3
    if day_cycle == 0:
        precip_prob = 75.0
        cloud_cover = 90.0
        condition = "Rain Expected"
        temp -= 4.0
    elif day_cycle == 1:
        precip_prob = 15.0
        cloud_cover = 40.0
        condition = "Partly Cloudy"
    else:
        precip_prob = 0.0
        cloud_cover = 10.0
        condition = "Sunny"
        
    return {
        "location": "Izmir, Turkey (Simulated)",
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

class AiAdviceRequest(BaseModel):
    device_id: int
    question: Optional[str] = None

class AiAdviceResponse(BaseModel):
    advice: str
    timestamp: datetime.datetime

@app.post("/api/ai/advise", response_model=AiAdviceResponse)
def get_ai_advice(
    req: AiAdviceRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify device exists and belongs to user
    device = db.query(models.Device).filter(models.Device.id == req.device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    farm = db.query(models.Farm).filter(models.Farm.id == device.farm_id, models.Farm.user_id == current_user.id).first()
    if not farm:
        raise HTTPException(status_code=403, detail="Unauthorized device access")
        
    # Get latest telemetry
    latest_telemetry = db.query(models.Telemetry).filter(
        models.Telemetry.device_id == req.device_id
    ).order_by(models.Telemetry.timestamp.desc()).first()
    
    moisture = latest_telemetry.soil_moisture if latest_telemetry else 50.0
    temp = latest_telemetry.temperature if latest_telemetry else 25.0
    humidity = latest_telemetry.humidity if latest_telemetry else 50.0
    ph = latest_telemetry.ph if latest_telemetry else 6.5
    
    # Get weather
    try:
        weather = get_weather_forecast()
    except Exception:
        weather = {
            "temperature": temp,
            "humidity": humidity,
            "precipitation_probability": 0.0,
            "cloud_cover": 0.0,
            "condition": "Sunny"
        }
        
    # Formulate Prompt
    weather_desc = f"{weather.get('condition', 'Sunny')} ({weather.get('temperature', 25.0)}°C, Humidity {weather.get('humidity', 50.0)}%, Rain Prob {weather.get('precipitation_probability', 0.0)}%, Cloud Cover {weather.get('cloud_cover', 0.0)}%)"
    
    prompt = (
        "You are the Smart Agri-Monitor AI Advisor.\n"
        "Here is the current state of the farm node:\n"
        f"- Device Name: {device.name}\n"
        f"- Soil Moisture: {moisture:.1f}% (volumetric)\n"
        f"- Soil pH: {ph:.2f}\n"
        f"- Air Temperature: {temp:.1f}°C\n"
        f"- Air Humidity: {humidity:.1f}%\n"
        f"- Current Weather Forecast: {weather_desc}\n\n"
    )
    
    if req.question:
        prompt += f"The farm supervisor has a specific question:\n\"{req.question}\"\n\n"
        prompt += (
            "Please answer this question directly, factoring in the current sensor telemetry and weather metrics. "
            "Address the user directly as a farming supervisor. Keep it concise (within 2-3 short paragraphs or bullet points) and practical."
        )
    else:
        prompt += (
            "Please provide a concise, high-value agronomic assessment and recommendations based on these conditions. "
            "Highlight soil moisture status (drought vs. waterlogged), pH health (optimal ranges are 6.0-7.5 for most crops), "
            "and suggest irrigation adjustments if necessary. "
            "Format your response as clean Markdown bullet points. Address the user directly as a farming supervisor. "
            "Keep the response brief (max 3-4 bullet points)."
        )
        
    # Query Gemini API
    advice = ""
    if GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            }
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code == 200:
                resp_data = resp.json()
                candidates = resp_data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        advice = parts[0].get("text", "").strip()
        except Exception:
            pass
            
    # Fallback to local rule-based advice if Gemini fails/is down/no key
    if not advice:
        recs = []
        if moisture < 25.0:
            recs.append("⚠️ **Critical Drought Warning**: Soil moisture is extremely low. Irrigate immediately to prevent crop wilting.")
        elif moisture < 45.0:
            recs.append("💧 **Low Moisture Alert**: Soil is dry. Schedule a moderate watering cycle soon.")
        elif moisture > 80.0:
            recs.append("🌊 **Waterlogged Soil**: Soil is overly saturated. Suspend irrigation to prevent root rot and aerate the soil.")
        else:
            recs.append("✅ **Moisture Nominal**: Soil moisture is in the optimal range (45-75%) for crop growth.")
            
        if ph < 5.5:
            recs.append("🧪 **Acidic Soil Alert**: pH level is acidic. Consider applying agricultural lime (calcium carbonate) to raise pH.")
        elif ph > 7.5:
            recs.append("🧪 **Alkaline Soil Alert**: pH level is alkaline. Consider applying elemental sulfur or organic compost to lower pH.")
        else:
            recs.append("✅ **pH Balanced**: Soil pH is neutral and highly suitable for nutrient absorption.")
            
        rain_prob = weather.get("precipitation_probability", 0.0)
        if rain_prob > 50.0:
            recs.append(f"🌧️ **Precipitation Forecasted**: High probability of rain ({rain_prob:.0f}%). The irrigation schedule is automatically scaled back to conserve water.")
            
        advice = "### Fallback AI Agronomic Assessment\n" + "\n".join(recs)
        if req.question:
            advice += f"\n\n*(Note: Gemini API is currently unavailable. Your question was: '{req.question}')*"
            
    return {
        "advice": advice,
        "timestamp": datetime.datetime.utcnow()
    }
