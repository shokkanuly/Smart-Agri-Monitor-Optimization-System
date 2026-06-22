from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    farms = relationship("Farm", back_populates="owner", cascade="all, delete-orphan")

class Farm(Base):
    __tablename__ = "farms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=True) # e.g. "Izmir, Turkey"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    owner = relationship("User", back_populates="farms")
    devices = relationship("Device", back_populates="farm", cascade="all, delete-orphan")

class Device(Base):
    __tablename__ = "devices"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, index=True, nullable=False)
    farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="active") # "active", "inactive", "maintenance"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    farm = relationship("Farm", back_populates="devices")
    telemetries = relationship("Telemetry", back_populates="device", cascade="all, delete-orphan")
    watering_logs = relationship("WateringLog", back_populates="device", cascade="all, delete-orphan")

class Telemetry(Base):
    __tablename__ = "telemetry"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
    soil_moisture = Column(Float, nullable=False) # percentage (0-100)
    ph = Column(Float, nullable=False) # soil pH level (0-14)
    temperature = Column(Float, nullable=False) # in Celsius
    humidity = Column(Float, nullable=False) # relative humidity (0-100)
    is_anomaly = Column(Boolean, default=False, nullable=False)
    
    device = relationship("Device", back_populates="telemetries")
    
    # Composite index for optimized time-series range queries on specific devices
    __table_args__ = (
        Index("idx_device_timestamp", "device_id", "timestamp"),
    )

class WateringLog(Base):
    __tablename__ = "watering_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True, nullable=False)
    duration_seconds = Column(Integer, nullable=False) # watering duration
    status = Column(String, default="completed") # "pending", "completed", "failed"
    manual_override = Column(Boolean, default=False, nullable=False)
    
    device = relationship("Device", back_populates="watering_logs")
