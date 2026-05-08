WEATHER_API_KEY = "aeda27a55450439591c91757260705"
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
        url = (
            f"http://api.weatherapi.com/v1/forecast.json?"
            f"key={WEATHER_API_KEY}"
            f"&q={lat},{lon}"
            f"&days=3"
            f"&aqi=no"
            f"&alerts=no"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        print("FULL API RESPONSE:", data)

        # 🚨 API error handling
        if "error" in data:
            print("API ERROR:", data["error"])
            return None, None, None, None, None, None, None

        current = data.get("current", {})
        forecast = data.get("forecast", {}).get("forecastday", [])

        # -----------------------------
        # TEMPERATURE
        # -----------------------------
        temp = current.get("temp_c")

        print("LIVE TEMP:", temp)

        # -----------------------------
        # CURRENT RAIN
        # -----------------------------
        current_precip = current.get("precip_mm", 0)

        condition_text = current.get("condition", {}).get("text", "").lower()

# 🌧 Only count as raining if actual precipitation exists
        if current_precip > 0.2:
             weather_code = 1
        else:
             weather_code = 0

        print("CONDITION:", condition_text)
        print("CURRENT PRECIP:", current_precip)
        print("WEATHER CODE:", weather_code)
        # -----------------------------
        # HOURLY DATA
        # -----------------------------
        recent_rain = 0
        current_hour_rain = current_precip

        if forecast:

            hourly_data = forecast[0].get("hour", [])

            # Last 12 hours rainfall
            recent_rain = sum(
                hour.get("precip_mm", 0)
                for hour in hourly_data[-12:]
            )

        print("RECENT RAIN:", recent_rain)

        # -----------------------------
        # FORECAST RAIN
        # -----------------------------
        forecast_rain = 0
        rain_day_index = None

        for i, day in enumerate(forecast):

            total_rain = day.get("day", {}).get("totalprecip_mm", 0)

            if total_rain > 2:
                forecast_rain = total_rain
                rain_day_index = i
                break

        print("FINAL TEMP:", temp)

        return (
            temp,
            current_precip,
            weather_code,
            current_hour_rain,
            recent_rain,
            forecast_rain,
            rain_day_index
        )

    except Exception as e:
        print("Weather error:", e)

        return None, None, None, None, None, None, None

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
        temp, current_precip, weather_code, current_hour_rain, recent_rain, forecast_rain, rain_day_index = get_weather_data(lat, lon)

# 🚨 Weather API failed
        if temp is None:
            return jsonify({
        "error": "Weather service temporarily unavailable. Please try again later."
        })

        print("LIVE TEMP:", temp)

        forecast_rain = forecast_rain or 0

        print("DEBUG:", weather_code, current_hour_rain, forecast_rain)

# 💧 Simulated Soil Moisture Score

        soil_moisture = 70

# Rain increases moisture
        soil_moisture += recent_rain * 2

# Temperature dries soil
        soil_moisture -= temp * 0.4

# Clamp between 0 and 100
        soil_moisture = max(0, min(100, soil_moisture))

        print("SOIL MOISTURE:", soil_moisture)



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


        # 💧 Simulated Soil Moisture Score

            soil_moisture = 70

# Recent rainfall increases moisture
            soil_moisture += recent_rain * 2

# Water balance affects moisture
            soil_moisture += water_balance * 5

# Higher temperatures dry soil faster
            soil_moisture -= temp * 0.3

# Keep within realistic bounds
            soil_moisture = max(0, min(100, soil_moisture))

        print("SOIL MOISTURE:", soil_moisture)


# 🌱 Crop Health Based on Soil Moisture

        if soil_moisture >= 70:
            crop_status = "Healthy"

        elif soil_moisture >= 45:
            crop_status = "Moderate Water Stress"

        else:
            crop_status = "High Water Stress"

# 🌍 Climate Impact Intelligence

# 💧 Estimated Water Savings (Liters)

        water_saved = 0

        if soil_moisture >= 70:
            water_saved = 150

        elif soil_moisture >= 45:
            water_saved = 70

        else:
            water_saved = 10


        # ♻️ Estimated CO₂ Avoided (kg)

        co2_avoided = round(water_saved * 0.004, 2)


        # 🌱 Sustainability Score

        if soil_moisture >= 70:
            sustainability = "High"

        elif soil_moisture >= 45:
            sustainability = "Moderate"

        else:
            sustainability = "Low"


        print("WATER SAVED:", water_saved)
        print("CO2 AVOIDED:", co2_avoided)
        print("SUSTAINABILITY:", sustainability)


        # 🚨 REAL-TIME RAIN OVERRIDE
        # 🚨 REAL-TIME RAIN OVERRIDE

        if current_precip > 0.5:

            crop_status = "Healthy"
            icon = "🟢"

            farmer_message = (
            "🌧️ It is currently raining on your farm. "
            "No irrigation needed."
            )

            advice = (
                "No irrigation needed. "
                "Rain is already watering your crops."
            )

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

        # 🌧 Rain timing intelligence

# Rain happening now
        if is_raining(weather_code) or current_hour_rain > 0.2:
            time_to_rain = 0

# Heavy recent rainfall (soil still moist)
        elif recent_rain >= 5:
            time_to_rain = 12

# Strong rain forecast soon
        elif forecast_rain >= 8:
            time_to_rain = 6

# Moderate rain forecast
        elif forecast_rain >= 3:
            time_to_rain = 24

# Light rain possibility
        elif forecast_rain > 0:
            time_to_rain = 48

# No meaningful rain expected
        else:
            time_to_rain = 999

# 🌧 FINAL DECISION BLOCK (FORCE PRIORITY)

        if current_precip > 0.5:
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


        if soil_moisture >= 70 and forecast_rain >= 3:
             ai_insight = (
        "Recent rainfall and favorable moisture conditions "
        "are supporting healthy crop growth."
        )

        elif soil_moisture >= 70:
            ai_insight = (
                "Soil moisture remains healthy despite current temperatures."
            )

        elif soil_moisture >= 45 and forecast_rain >= 3:
            ai_insight = (
                "Rainfall expected soon may help stabilize declining soil moisture."
            )

        elif soil_moisture >= 45:
            ai_insight = (
                "Soil moisture is gradually decreasing under current weather conditions."
            )

        else:
            ai_insight = (
                "High temperatures and limited rainfall are increasing crop water stress."
            )

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
            "soil_moisture": round(soil_moisture, 1),
            "water_saved": water_saved,
            "co2_avoided": co2_avoided,
            "sustainability": sustainability,
            "ai_insight": ai_insight,   # ✅ ADD THIS LINE
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
