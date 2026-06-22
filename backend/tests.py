import unittest
import os
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test DB environment before imports
os.environ["DATABASE_URL"] = "sqlite:///./test_agri_monitor.db"

import database
import models
import auth
import prediction_engine

class TestAgriMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create test database tables
        models.Base.metadata.create_all(bind=database.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=database.engine)
        
    @classmethod
    def tearDownClass(cls):
        # Clean up database file
        models.Base.metadata.drop_all(bind=database.engine)
        if os.path.exists("test_agri_monitor.db"):
            os.remove("test_agri_monitor.db")
        if os.path.exists("irrigation_model.pkl"):
            os.remove("irrigation_model.pkl")

    def setUp(self):
        self.db = self.SessionLocal()
        
    def tearDown(self):
        self.db.query(models.WateringLog).delete()
        self.db.query(models.Telemetry).delete()
        self.db.query(models.Device).delete()
        self.db.query(models.Farm).delete()
        self.db.query(models.User).delete()
        self.db.commit()
        self.db.close()

    def test_user_creation_and_auth(self):
        # Hash password and verify
        raw_password = "securepassword123"
        hashed = auth.get_password_hash(raw_password)
        self.assertTrue(auth.verify_password(raw_password, hashed))
        self.assertFalse(auth.verify_password("wrongpassword", hashed))
        
        # Test DB insertion
        user = models.User(username="turkey_scholar", hashed_password=hashed)
        self.db.add(user)
        self.db.commit()
        
        fetched = self.db.query(models.User).filter_by(username="turkey_scholar").first()
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.username, "turkey_scholar")
        
        # Access Token test
        token = auth.create_access_token({"sub": fetched.username})
        self.assertIsNotNone(token)

    def test_farm_and_device_relationship(self):
        # Create user
        user = models.User(username="farmer_joe", hashed_password="hashedpassword")
        self.db.add(user)
        self.db.commit()
        
        # Create farm
        farm = models.Farm(name="Anatolian Olive Grove", location="Izmir, Turkey", user_id=user.id)
        self.db.add(farm)
        self.db.commit()
        
        # Create device
        device = models.Device(name="Olive Soil Sensor Node 1", api_key="node-olive-1", farm_id=farm.id)
        self.db.add(device)
        self.db.commit()
        
        # Verify query relationships
        fetched_farm = self.db.query(models.Farm).filter_by(id=farm.id).first()
        self.assertEqual(len(fetched_farm.devices), 1)
        self.assertEqual(fetched_farm.devices[0].name, "Olive Soil Sensor Node 1")

    def test_telemetry_time_series_insertion(self):
        user = models.User(username="sensor_guy", hashed_password="hashedpassword")
        self.db.add(user)
        self.db.commit()
        
        farm = models.Farm(name="Cotton Field A", location="Adana, Turkey", user_id=user.id)
        self.db.add(farm)
        self.db.commit()
        
        device = models.Device(name="Sensor node", api_key="sensor-key", farm_id=farm.id)
        self.db.add(device)
        self.db.commit()
        
        # Write multiple telemetries simulating a time-series stream
        for i in range(5):
            tel = models.Telemetry(
                device_id=device.id,
                soil_moisture=45.0 + i,
                ph=6.2,
                temperature=24.0 + (i * 0.5),
                humidity=55.0 - i,
                is_anomaly=False
            )
            self.db.add(tel)
        self.db.commit()
        
        # Verify indexing count
        readings = self.db.query(models.Telemetry).filter_by(device_id=device.id).all()
        self.assertEqual(len(readings), 5)
        self.assertEqual(readings[0].soil_moisture, 45.0)
        self.assertEqual(readings[4].soil_moisture, 49.0)

    def test_predictive_engine(self):
        # Test procedural math Evapotranspiration calculation
        et = prediction_engine.calculate_evapotranspiration(temp=32.0, humidity=40.0)
        self.assertTrue(et > 0.0)
        
        # Test procedural watering
        water_duration = prediction_engine.procedural_watering_estimate(
            current_moisture=35.0,
            target_moisture=65.0,
            temp=28.0,
            humidity=45.0
        )
        # Should need water since 35 < 65
        self.assertTrue(water_duration > 0.0)
        
        # Test ML predictor model (triggers training if file doesn't exist)
        ml_duration = prediction_engine.predict_watering_duration(
            current_moisture=40.0,
            temperature=30.0,
            humidity=50.0,
            ph=6.5,
            precip_prob=10.0,
            cloud_cover=20.0
        )
        self.assertTrue(ml_duration >= 0.0)

if __name__ == "__main__":
    unittest.main()
