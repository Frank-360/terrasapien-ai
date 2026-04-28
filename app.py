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
# LOGIC
# ---------------------------
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

def vegetation_health():
    ndvi = round(random.uniform(0.2,0.8),2)
    if ndvi > 0.6:
        return ndvi, "Healthy vegetation"
    elif ndvi > 0.4:
        return ndvi, "Moderate vegetation"
    return ndvi, "Poor vegetation"

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
        try:
            temp, rain, forecast = get_weather_data(lat, lon)
        except:
            temp, rain, forecast = 30, 2, 5

        temp = temp or 30
        rain = rain or 1

        # 🌧 Rain calculation
        evaporation_factor = 1 + (temp - 25) * 0.02
        total_rain = forecast / evaporation_factor

        if zone == "North":
            total_rain *= 0.8
        else:
            total_rain *= 1.1

        # 🌾 Crop thresholds
        low_rain = 5
        moderate_rain = 10

        if crop == "Rice":
            low_rain, moderate_rain = 8, 15
        elif crop == "Cassava":
            low_rain, moderate_rain = 4, 9
        elif crop == "Millet":
            low_rain, moderate_rain = 3, 7

        if zone == "North":
            low_rain += 1
            moderate_rain += 2

        # 🌱 Crop status
        if total_rain < low_rain:
            crop_status = "High Water Stress"
            icon = "🔴"
        elif total_rain < moderate_rain:
            crop_status = "Moderate Water Stress"
            icon = "🟡"
        else:
            crop_status = "Healthy"
            icon = "🟢"

        # 🌱 Advice
        if crop_status == "High Water Stress":
            advice = "Water immediately. Very dry conditions." if zone == "North" else "Water your crops now."
        elif crop_status == "Moderate Water Stress":
            advice = "Water soon, rain may delay." if zone == "North" else "Monitor crops, may need water."
        else:
            advice = "Keep monitoring due to dry conditions." if zone == "North" else "No irrigation needed."

        # 👨‍🌾 Farmer message
        if crop_status == "Healthy":
            farmer_message = "Your crops are doing well. No action needed."
        elif crop_status == "Moderate Water Stress":
            farmer_message = "Your crops are starting to get dry."
        else:
            farmer_message = "Your crops need water urgently."

        # 🌿 Vegetation
        ndvi = min(round(0.4 + (rain / 20), 2), 0.8)

        if ndvi > 0.6:
            veg = "Healthy vegetation"
        elif ndvi > 0.4:
            veg = "Moderate vegetation"
        else:
            veg = "Poor vegetation"

        # 🤖 AI water saving
        reduction = max(estimate_ai_water_saving(rain, temp, 0.6), 10)

        # 🌍 Carbon
        carbon = estimate_carbon(farm_size, crop)
        credits, usd = carbon_credits(method, frequency, farm_size, reduction)

        # 🌧 Rain timing
        if forecast > 10:
            time_to_rain = 6
        elif forecast > 5:
            time_to_rain = 24
        else:
             time_to_rain = 48

        # 🌱 Season
        month = datetime.datetime.now().month
        season = "Dry Season" if month in [11,12,1,2,3] else "Rainy Season"

        # 📊 Score
        score = min(int((carbon * 10) + (total_rain * 2)), 100)

        return jsonify({
            "season": season,
            "crop_status": crop_status,
            "farmer_message": farmer_message,
            "advice": advice,
            "icon": icon,
            "temperature": temp,
            "rain_5days": round(total_rain, 2),
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
    
  