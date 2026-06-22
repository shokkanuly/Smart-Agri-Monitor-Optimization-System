import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import os
import pickle

MODEL_FILE = "irrigation_model.pkl"

def calculate_evapotranspiration(temp: float, humidity: float, solar_radiation: float = 15.0) -> float:
    """
    Simplified Hargreaves/Penman-Monteith procedural calculation for Reference Evapotranspiration (ET0).
    Estimates water loss in mm/day based on temperature and relative humidity.
    """
    # Hargreaves method approximation
    # ET0 = 0.0023 * (Tmean + 17.8) * (Tmax - Tmin)^0.5 * Ra
    # Here we approximate with current temp and humidity
    humidity_factor = max(0.1, 1.0 - (humidity / 100.0))
    et0 = 0.0018 * (temp + 17.8) * (solar_radiation ** 0.5) * humidity_factor
    return max(0.0, et0)

def procedural_watering_estimate(
    current_moisture: float,
    target_moisture: float = 65.0,
    temp: float = 25.0,
    humidity: float = 50.0,
    soil_type_coeff: float = 15.0 # Seconds per % moisture deficit
) -> float:
    """
    Procedural rule-based calculation of watering duration.
    """
    if current_moisture >= target_moisture:
        return 0.0
        
    moisture_deficit = target_moisture - current_moisture
    et = calculate_evapotranspiration(temp, humidity)
    
    # Base duration to replenish deficit, augmented by current rate of water loss (ET)
    duration = moisture_deficit * soil_type_coeff * (1.0 + et * 0.1)
    return max(0.0, duration)

# Train a simple model on synthetic agricultural physics data to represent historical system learning
def generate_synthetic_data(num_samples=1000):
    np.random.seed(42)
    
    # Features
    current_moisture = np.random.uniform(20.0, 80.0, num_samples)
    temperature = np.random.uniform(15.0, 40.0, num_samples)
    humidity = np.random.uniform(20.0, 95.0, num_samples)
    ph = np.random.uniform(5.5, 7.5, num_samples)
    precipitation_probability = np.random.uniform(0.0, 100.0, num_samples) # weather forecast
    cloud_cover = np.random.uniform(0.0, 100.0, num_samples) # weather forecast
    
    # Target: Optimal watering duration (seconds)
    # Target moisture is 65%. If moisture >= 65%, watering duration is 0.
    # Higher temperature, lower humidity, lower precipitation probability increase duration.
    durations = []
    for i in range(num_samples):
        target = 65.0
        moisture = current_moisture[i]
        
        if moisture >= target:
            durations.append(0.0)
            continue
            
        deficit = target - moisture
        et = calculate_evapotranspiration(temperature[i], humidity[i])
        
        # If precipitation is highly likely (> 70%), we scale down watering duration to save water
        rain_save_factor = 1.0
        if precipitation_probability[i] > 70.0:
            rain_save_factor = 0.1
        elif precipitation_probability[i] > 40.0:
            rain_save_factor = 0.5
            
        # Cloud cover slightly reduces evaporation rate
        cloud_factor = 1.0 - (cloud_cover[i] / 200.0)
        
        duration = deficit * 15.0 * (1.0 + et * 0.08 * cloud_factor) * rain_save_factor
        durations.append(max(0.0, duration))
        
    df = pd.DataFrame({
        "current_moisture": current_moisture,
        "temperature": temperature,
        "humidity": humidity,
        "ph": ph,
        "precipitation_probability": precipitation_probability,
        "cloud_cover": cloud_cover,
        "watering_duration": durations
    })
    return df

def train_predictive_model():
    """
    Trains the scikit-learn Random Forest model on historical data.
    """
    df = generate_synthetic_data()
    X = df[["current_moisture", "temperature", "humidity", "ph", "precipitation_probability", "cloud_cover"]]
    y = df["watering_duration"]
    
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)
    
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(model, f)
        
    return model

def load_or_train_model():
    if os.path.exists(MODEL_FILE):
        try:
            with open(MODEL_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return train_predictive_model()
    else:
        return train_predictive_model()

# Global reference to the loaded model
model = load_or_train_model()

def predict_watering_duration(
    current_moisture: float,
    temperature: float,
    humidity: float,
    ph: float,
    precip_prob: float,
    cloud_cover: float
) -> float:
    """
    Incorporate ML predictive scheduling. Returns recommended duration in seconds.
    """
    global model
    if model is None:
        model = load_or_train_model()
        
    features = np.array([[current_moisture, temperature, humidity, ph, precip_prob, cloud_cover]])
    prediction = model.predict(features)[0]
    return float(max(0.0, prediction))
