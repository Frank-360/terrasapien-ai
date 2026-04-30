from flask import Flask, request, jsonify
import requests
from flask_cors import CORS
import datetime

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ---------------------------
# HELPER: RAIN DETECTION
# ---------------------------
def is_raining(code):
    return code in [51, 53, 55, 61, 63, 65, 80, 81, 82]

# ---------------------------
# WEATHER
# ---------------------------
def get_weather_data(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,weathercode&hourly=precipitation&daily=precipitation_sum&timezone=auto"

        data = requests.get(url, timeout=5).json()

        current = data.get("current", {})
        hourly = data.get("hourly", {})

        temp = current.get("temperature_2m")
# SAFE fallback (DO NOT REMOVE)
        if temp is None:
            temp = 30
        current_precip = current.get("precipitation", 0)
        weather_code = current.get("weathercode", -1)

        hourly_precip = hourly.get("precipitation", [])
        current_hour_rain = hourly_precip[0] if hourly_precip else 0

        daily = data.get("daily", {}).get("precipitation_sum", [])

        forecast_rain = 0
        rain_day_index = None

        for i, rain in enumerate(daily):
            if rain > 2:
                forecast_rain = rain
                rain_day_index = i
                break

        return temp, current_precip, weather_code, current_hour_rain, forecast_rain, rain_day_index

    except Exception as e:
        print("Weather error:", e)
        return 30, 0, -1, 0, 0, None

# ---------------------------
# AGRI LOGIC
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
# MAIN ROUTE
# ---------------------------
@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json(silent=True) or {}

        lat = data.get("lat", 7.38)
        lon = data.get("lon", 3.93)

        zone = "North" if lat > 10 else "South"

        crop = data.get("crop", "Maize")
        farm_size = data.get("farm_size", 1)

        method = data.get("method", "Manual (bucket)")
        frequency = data.get("frequency", "Weekly")

        # 🌤 Weather
        temp, current_precip, weather_code, current_hour_rain, forecast_rain, rain_day_index = get_weather_data(lat, lon)

        temp = temp or 30
        forecast_rain = forecast_rain or 0

        print("DEBUG:", weather_code, current_hour_rain, forecast_rain)

        # 🌱 Soil
        soil = 0.5 if zone == "North" else 0.7

        # 🌿 Evapotranspiration
        et = evapotranspiration(temp, crop)

        # 🌧 Rain balance
        effective_rain = (current_hour_rain * 0.7) + (forecast_rain * 0.3)
        daily_rain = effective_rain / 5
        water_balance = daily_rain - et

        if zone == "North":
            water_balance *= 0.8
        else:
            water_balance *= 1.1

        # 🚨 REAL-TIME RAIN OVERRIDE
        if is_raining(weather_code) or current_hour_rain > 0.2:
            crop_status = "Healthy"
            icon = "🟢"
            farmer_message = "🌧️ It is currently raining on your farm. No irrigation needed."
            advice = "No irrigation needed. Rain is already watering your crops."

        else:
            # 🌱 Crop status
            if water_balance < -2:
                crop_status = "High Water Stress"
                icon = "🔴"
            elif water_balance < 0:
                crop_status = "Moderate Water Stress"
                icon = "🟡"
            else:
                crop_status = "Healthy"
                icon = "🟢"

            # 💧 Irrigation advice
            if crop_status == "High Water Stress":
                advice = "Apply water immediately. Soil moisture is critically low."
                farmer_message = "Your crops are very dry. Water them now."
            elif crop_status == "Moderate Water Stress":
                advice = "Irrigate within 24 hours to prevent crop stress."
                farmer_message = "Your crops are starting to dry."
            else:
                advice = "No irrigation needed now. Continue monitoring."
                farmer_message = "Your crops are doing well."

        # 🌿 NDVI
        ndvi = min(max((forecast_rain / 50), 0.2), 0.8)

        if ndvi > 0.6:
            veg = "Healthy vegetation"
        elif ndvi > 0.4:
            veg = "Moderate vegetation"
        else:
            veg = "Poor vegetation"

        # 🤖 Water saving
        reduction = max(estimate_ai_water_saving(forecast_rain, temp, soil), 10)

        # 🌍 Carbon
        carbon = estimate_carbon(farm_size, crop)
        credits, usd = carbon_credits(method, frequency, farm_size, reduction)

 # 🌧 Rain timing (FIXED THRESHOLDS)

        if is_raining(weather_code) or current_hour_rain > 0.2:
             time_to_rain = 0

        elif forecast_rain >= 3:
            time_to_rain = 6   # rain soon (THIS WAS YOUR PROBLEM)

        elif forecast_rain >= 1:
             time_to_rain = 24  # moderate chance

        elif forecast_rain > 0:
             time_to_rain = 48

        else:
            time_to_rain = 999   # means "no rain expected"

# 🌧 FINAL DECISION BLOCK (FORCE PRIORITY)

        if time_to_rain == 0:
            advice = "It is raining now. No irrigation needed."
            farmer_message = "🌧️ It is currently raining. No need to water your crops."

        elif time_to_rain is not None and time_to_rain <= 6:
            advice = "Rain expected within hours. Delay irrigation."
            farmer_message = "Rain is expected shortly. Hold off watering for now."

        else:
    # ONLY now consider crop stress
            if crop_status == "High Water Stress":
                advice = "Apply water immediately."
            elif crop_status == "Moderate Water Stress":
                advice = "Irrigate within 24 hours."
            else:
                 advice = "No irrigation needed now."

       # 🤖 AI Insight (ALWAYS ASSIGNED)

        if time_to_rain == 0:
             ai_insight = "Rain is already providing sufficient water."

        elif time_to_rain is not None and time_to_rain <= 6:
            ai_insight = "Rain is expected soon, so irrigation can be delayed."

        elif time_to_rain is not None and time_to_rain <= 24:
            ai_insight = "Rain may occur today, monitor soil before irrigating."

        elif crop_status == "High Water Stress":
            ai_insight = "Crops are under severe stress due to low moisture."

        elif crop_status == "Moderate Water Stress":
             ai_insight = "Soil moisture is decreasing and may affect crop growth."

        else:
            ai_insight = "Conditions are stable with no immediate risk."

        # 🌱 Season
        month = datetime.datetime.now().month
        season = "Dry Season" if month in [11,12,1,2,3] else "Rainy Season"

        # 📊 Score
        score = min(int((carbon * 10) + (forecast_rain * 2)), 100)

        print("FINAL OUTPUT →", advice, "| time_to_rain:", time_to_rain)

        print("AI INSIGHT:", ai_insight)

        return jsonify({
            "season": season,
            "crop_status": crop_status,
            "farmer_message": farmer_message,
            "advice": advice,
            "icon": icon,
            "temperature": temp,
            "rain_5days": round(forecast_rain, 2),
            "time_to_rain": time_to_rain,
            "ndvi": ndvi,
            "vegetation_status": veg,
            "water_saving": reduction,
            "carbon": carbon,
            "carbon_credits": credits,
            "carbon_value_usd": usd,
            "climate_score": score,
            "ai_insight": ai_insight,   # ✅ ADD THIS LINE
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)