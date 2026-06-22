/**
 * Smart Agri-Monitor & Optimization System - ESP32 Firmware
 * 
 * Features:
 *  - High-frequency sensor polling.
 *  - Edge Processing: Moving average filter (window size = 10) to smooth high-frequency noise.
 *  - Edge Anomaly Detection: Checks if soil moisture drops below threshold or if temperature spikes.
 *  - Adaptive Telemetry Throttling: Sends alerts immediately for anomalies, otherwise transmits 
 *    processed averages at power-saving intervals (e.g., every 5 minutes).
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h> // Library: ArduinoJson by Benoit Blanchon

// Network Configurations
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// API Configurations
const char* serverUrl = "http://127.0.0.1:8000/api/telemetry"; // Replace with backend IP
const char* apiKey = "node-your-device-api-key";             // Unique API Key from registration

// Sensor Pins
#define SOIL_MOISTURE_PIN 34
#define PH_PIN            35
#define TEMP_HUMID_PIN    32 // Assuming DHT22 sensor

// Edge Processing Configurations
const int WINDOW_SIZE = 10;
float moistureBuffer[WINDOW_SIZE];
float phBuffer[WINDOW_SIZE];
float tempBuffer[WINDOW_SIZE];
float humidityBuffer[WINDOW_SIZE];
int bufferIndex = 0;
bool bufferFull = false;

// Adaptive Telemetry Intervals (Milliseconds)
unsigned long lastTransmissionTime = 0;
const unsigned long STANDARD_INTERVAL = 300000; // 5 minutes (300,000 ms) in production
const unsigned long ANOMALY_COOLDOWN = 10000;   // Wait 10 seconds between anomaly alerts

// Anomaly Thresholds
const float CRITICAL_LOW_MOISTURE = 15.0; // Soil is critically dry
const float CRITICAL_HIGH_TEMP = 45.0;    // Extreme heat stress
const float CRITICAL_LOW_PH = 4.5;        // Acidic soil hazard
const float CRITICAL_HIGH_PH = 8.5;       // Alkaline soil hazard

void setup() {
  Serial.begin(115200);
  
  // Initialize Wi-Fi
  connectWiFi();
  
  // Clear buffers
  for (int i = 0; i < WINDOW_SIZE; i++) {
    moistureBuffer[i] = 0.0;
    phBuffer[i] = 0.0;
    tempBuffer[i] = 0.0;
    humidityBuffer[i] = 0.0;
  }
}

void loop() {
  // 1. Read raw sensors
  float rawMoisture = readSoilMoistureSensor();
  float rawPh = readPhSensor();
  float rawTemp = readTemperatureSensor();
  float rawHumidity = readHumiditySensor();
  
  // 2. Perform Edge Processing (Moving Average Filter)
  updateBuffers(rawMoisture, rawPh, rawTemp, rawHumidity);
  
  if (bufferFull) {
    float avgMoisture = getAverage(moistureBuffer);
    float avgPh = getAverage(phBuffer);
    float avgTemp = getAverage(tempBuffer);
    float avgHumidity = getAverage(humidityBuffer);
    
    // 3. Perform Edge Anomaly Detection
    bool isAnomaly = checkAnomalies(avgMoisture, avgPh, avgTemp, avgHumidity);
    
    unsigned long currentTime = millis();
    
    // 4. Adaptive Transmission Logic
    if (isAnomaly) {
      // Immediate transmission if an anomaly is detected and we are out of cooldown
      if (currentTime - lastTransmissionTime >= ANOMALY_COOLDOWN) {
        Serial.println("[EDGE WARNING] Anomaly detected! Initiating immediate alert payload transmission...");
        transmitTelemetry(avgMoisture, avgPh, avgTemp, avgHumidity, true);
        lastTransmissionTime = currentTime;
      }
    } else {
      // Standard throttled transmission
      if (currentTime - lastTransmissionTime >= STANDARD_INTERVAL || lastTransmissionTime == 0) {
        Serial.println("[EDGE INFO] Standard transmission interval reached. Transmitting averaged sensor metrics...");
        transmitTelemetry(avgMoisture, avgPh, avgTemp, avgHumidity, false);
        lastTransmissionTime = currentTime;
      }
    }
  } else {
    Serial.println("[EDGE INFO] Filling buffer. Waiting for complete sliding window...");
  }
  
  delay(1000); // Poll sensors every second
}

// --- Helper Functions ---

void connectWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected successfully!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

float readSoilMoistureSensor() {
  // Simulating hardware analog read conversion to percentage (0 - 100%)
  int analogValue = analogRead(SOIL_MOISTURE_PIN);
  float percentage = map(analogValue, 4095, 1500, 0, 100); // 4095 dry, 1500 fully wet
  return constrain(percentage, 0.0, 100.0);
}

float readPhSensor() {
  // Simulating hardware voltage translation to pH scale (0.0 - 14.0)
  int analogValue = analogRead(PH_PIN);
  float voltage = analogValue * (3.3 / 4095.0);
  float phValue = 3.5 * voltage; // Simulates pH response
  return constrain(phValue, 0.0, 14.0);
}

float readTemperatureSensor() {
  // Returns temperature in Celsius from DHT sensor
  // Under hardware, use dht.readTemperature()
  return 24.5; 
}

float readHumiditySensor() {
  // Returns relative humidity percentage
  // Under hardware, use dht.readHumidity()
  return 55.0;
}

void updateBuffers(float moisture, float ph, float temp, float humidity) {
  moistureBuffer[bufferIndex] = moisture;
  phBuffer[bufferIndex] = ph;
  tempBuffer[bufferIndex] = temp;
  humidityBuffer[bufferIndex] = humidity;
  
  bufferIndex++;
  if (bufferIndex >= WINDOW_SIZE) {
    bufferIndex = 0;
    bufferFull = true;
  }
}

float getAverage(float buffer[]) {
  float sum = 0.0;
  for (int i = 0; i < WINDOW_SIZE; i++) {
    sum += buffer[i];
  }
  return sum / WINDOW_SIZE;
}

bool checkAnomalies(float moisture, float ph, float temp, float humidity) {
  if (moisture < CRITICAL_LOW_MOISTURE) return true;
  if (temp > CRITICAL_HIGH_TEMP) return true;
  if (ph < CRITICAL_LOW_PH || ph > CRITICAL_HIGH_PH) return true;
  return false;
}

void transmitTelemetry(float moisture, float ph, float temp, float humidity, bool isAnomaly) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[ERROR] Wi-Fi disconnected. Cannot transmit telemetry.");
    return;
  }
  
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Api-Key", apiKey);
  
  // Construct JSON Payload
  StaticJsonDocument<200> doc;
  doc["soil_moisture"] = moisture;
  doc["ph"] = ph;
  doc["temperature"] = temp;
  doc["humidity"] = humidity;
  
  String jsonPayload;
  serializeJson(doc, jsonPayload);
  
  int httpResponseCode = http.POST(jsonPayload);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.print("[HTTP RESPONSE] ");
    Serial.println(httpResponseCode);
    Serial.println(response);
  } else {
    Serial.print("[HTTP ERROR] Post failed, error: ");
    Serial.println(http.errorToString(httpResponseCode).c_str());
  }
  http.end();
}
