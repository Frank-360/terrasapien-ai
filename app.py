from flask import Flask, request, jsonify
import requests
import random
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ---------------------------
# WEATHER
# ---------------------------
def get_weather_data(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation&daily=precipitation_sum"
        data = requests.get(url, timeout=5).json()

        temp = data["current"]["temperature_2m"]
        rain_today = data["current"]["precipitation"]

        forecast = data["daily"]["precipitation_sum"][:5]
        total_forecast = sum(forecast)

        return temp, rain_today, total_forecast
    except Exception as e:
        print("Weather error:", e)
        return 30, 0, 5

# ---------------------------
# ADVANCED AGRI LOGIC
# ---------------------------
def evapotranspiration(temp, crop):
    et0 = 0.0023 * (temp + 17)

    kc = {
        "Maize": 1.2,
        "Rice": 1.1,
        "Cassava": 0.9,
        "Millet": 0.7
    }

    return et0 * kc.get(crop, 1.0)

def estimate_ai_water_saving(rainfall, temperature, soil):
    saving = 0
    if rainfall > 10:
        saving += 20
    if soil > 0.6:
        saving += 30
    if temperature > 35:
        saving -= 10
    return max(0, min(saving, 50))

def estimate_carbon(farm_size, crop):
    factors = {"Maize":0.6,"Rice":0.8,"Cassava":0.5,"Millet":0.4}
    return round(farm_size * factors.get(crop,0.5),2)

# ---------------------------
# CARBON CREDIT SYSTEM
# ---------------------------
def estimate_water_usage(method, freq, farm_size):
    base = {"Rain-fed":0,"Manual (bucket)":200,"Small pump":800,"Large pump":2000}
    frequency = {"Rarely":0.5,"Weekly":1,"2-3 times/week":2,"Daily":4}
    return base.get(method,200) * frequency.get(freq,1) * farm_size

def pump_type(method):
    return {"Manual (bucket)":"manual","Small pump":"electric","Large pump":"diesel"}.get(method,"manual")

def carbon_credits(method, freq, farm_size, reduction):
    factors = {"diesel":2.68,"electric":0.5,"manual":0}
    water = estimate_water_usage(method, freq, farm_size)
    pump = pump_type(method)

    saved = (water * reduction/100) * factors[pump] / 1000
    credits = saved / 1000
    usd_value = credits * 10

    return round(credits,4), round(usd_value,2)

# ---------------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        import datetime

        data = request.get_json(silent=True) or {}

        lat = data.get("lat", 7.38)
        lon = data.get("lon", 3.93)

        # 🌍 Region
        zone = "North" if lat > 10 else "South"

        crop = data.get("crop", "Maize")
        farm_size = data.get("farm_size", 1)

        method = data.get("method", "Manual (bucket)")
        frequency = data.get("frequency", "Weekly")

        # 🌤 Weather
        temp, rain, forecast = get_weather_data(lat, lon)
        current_rain = rain or 0

        temp = temp or 30
        forecast = forecast or 5

        # 🌱 Soil (region-based realism)
        soil = 0.5 if zone == "North" else 0.7

        # 🌿 Evapotranspiration (REAL CORE)
        et = evapotranspiration(temp, crop)

        # 🌧 Daily rainfall
        # Combine current + forecast rain
        effective_rain = (current_rain * 0.7) + (forecast * 0.3)

        daily_rain = effective_rain / 5
        water_balance = daily_rain - et

        # 💧 WATER BALANCE ENGINE
        water_balance = daily_rain - et

        if zone == "North":
            water_balance *= 0.8
        else:
            water_balance *= 1.1

        # 🌱 Crop status (NEW INTELLIGENCE)
        if water_balance < -2:
            crop_status = "High Water Stress"
            icon = "🔴"
        elif water_balance < 0:
            crop_status = "Moderate Water Stress"
            icon = "🟡"
        else:
            crop_status = "Healthy"
            icon = "🟢"

        # 💧 Irrigation timing engine
        if crop_status == "High Water Stress":
            irrigation_hours = 0
        elif crop_status == "Moderate Water Stress":
            irrigation_hours = 24
        else:
            irrigation_hours = 72

        # 🌱 Advice (now intelligent)
        if irrigation_hours == 0:
            advice = "Apply water immediately. Soil moisture is critically low."
        elif irrigation_hours == 24:
            advice = "Irrigate within 24 hours to prevent crop stress."
        else:
            advice = "No irrigation needed now. Continue monitoring."

       # 👨‍🌾 Farmer message
        if crop_status == "Healthy":
            farmer_message = "Your crops are doing well."
        elif crop_status == "Moderate Water Stress":
            farmer_message = "Your crops are starting to dry."
        else:
            farmer_message = "Your crops are very dry. Water them now."

        # 🚨 REAL-TIME RAIN OVERRIDE (CRITICAL FIX)
        if current_rain > 0.1:
            crop_status = "Healthy"
            icon = "🟢"
            farmer_message = "It is currently raining on your farm."
            advice = "No irrigation needed. Rain is already watering your crops."
        # 🌿 Improved NDVI (based on rainfall)
        ndvi = min(max((forecast / 50), 0.2), 0.8)

        if ndvi > 0.6:
            veg = "Healthy vegetation"
        elif ndvi > 0.4:
            veg = "Moderate vegetation"
        else:
            veg = "Poor vegetation"

        # 🤖 Water saving
        reduction = max(estimate_ai_water_saving(forecast, temp, soil), 10)

        # 🌍 Carbon
        carbon = estimate_carbon(farm_size, crop)
        credits, usd = carbon_credits(method, frequency, farm_size, reduction)

       
             # 🌧 Rain timing (REAL-TIME FIXED)
        if current_rain > 0.1:
             time_to_rain = 0
        elif forecast > 10:
            time_to_rain = 6
        elif forecast > 5:
            time_to_rain = 24
        else:
             time_to_rain = 48

        # 🌱 Season
        month = datetime.datetime.now().month
        season = "Dry Season" if month in [11,12,1,2,3] else "Rainy Season"

        # 📊 Score
        score = min(int((carbon * 10) + (forecast * 2)), 100)

        return jsonify({
            "season": season,
            "crop_status": crop_status,
            "farmer_message": farmer_message,
            "advice": advice,
            "icon": icon,
            "temperature": temp,
            "rain_5days": round(forecast, 2),
            "time_to_rain": time_to_rain,
            "ndvi": ndvi,
            "vegetation_status": veg,
            "water_saving": reduction,
            "carbon": carbon,
            "carbon_credits": credits,
            "carbon_value_usd": usd,
            "climate_score": score
        })
    except Exception as e:
                return jsonify({"error": str(e)})