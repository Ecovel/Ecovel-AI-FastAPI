import re
import json
import requests
import os
from math import radians, cos, sin, sqrt, atan2
from googletrans import Translator
from google.generativeai import configure, GenerativeModel
from app.schemas import TravelRequest, TravelResponse
from dotenv import load_dotenv

load_dotenv()
KAKAO_API_KEY = os.getenv("KAKAO_REST_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TOURAPI_KEY = os.getenv("TOURAPI_SERVICE_KEY")

configure(api_key=GEMINI_API_KEY)
model = GenerativeModel("gemini-1.5-flash")
translator = Translator()

PLACE_NAME_MAP = {
    "Jeju Green Road Trail": "Jeju Green Road",
    "Beach where plogging is allowed": "Iho Tewoo Beach",
    "Gotjawal Forest Trail Trekking Course": "Gotjawal",
    "Jeju Traditional House Experience": "Jeju Folk Village",
    "Udo Lighthouse Observatory": "Udo Lighthouse Park",
    "Café with Ocean View": "Beach Cafe",
    "Tangerine Farm Experience": "Tangerine Experience Farm",
    "Jeju Renewable Energy Theme Park": "Energy Future Museum",
    "Café with Ocean View": "Beach Cafe",
    "Udo Beach Cafe (Eco-friendly certification)": "Udo Cafe",
    "Farms where you can participate in the Jeju Flow Program": "Jeju Rural Experience Village"
}

def get_google_place_image(place_name: str, api_key: str) -> str:
    query = f"Jeju {place_name}"
    find_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id",
        "key": api_key
    }
    res = requests.get(find_url, params=params).json()
    if not res.get("candidates"):
        return None
    place_id = res["candidates"][0]["place_id"]

    detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "photo",
        "key": api_key
    }
    res = requests.get(detail_url, params=params).json()
    photos = res.get("result", {}).get("photos", [])
    if not photos:
        return None
    photo_ref = photos[0]["photo_reference"]
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={api_key}"

def get_place_image_url(place_id: str, place_name: str):
    google_url = get_google_place_image(place_name, GOOGLE_API_KEY)
    if google_url:
        return google_url
    return f"https://place.map.kakao.com/{place_id}/photo"

def get_place_from_kakao(keyword: str, district: str):
    keyword = PLACE_NAME_MAP.get(keyword, keyword)
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": keyword}
    res = requests.get("https://dapi.kakao.com/v2/local/search/keyword.json", headers=headers, params=params)
    if res.status_code == 200:
        docs = res.json().get("documents", [])
        for doc in docs:
            if "제주" in doc.get("address_name", ""):
                return {
                    "id": doc["id"],
                    "name": doc["place_name"],
                    "lat": float(doc["y"]),
                    "lon": float(doc["x"]),
                    "address": doc.get("address_name", ""),
                    "imageUrl": get_place_image_url(doc["id"], doc["place_name"])
                }
    return None

def translate_place_name(korean_name: str) -> str:
    try:
        translated = translator.translate(korean_name, src='ko', dest='en')
        return translated.text
    except:
        return korean_name

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def estimate_travel_time_km(distance_km, mode):
    if mode == "walk":
        return distance_km / 5 * 60
    elif mode == "bicycle":
        return distance_km / 15 * 60
    elif mode == "public":
        return distance_km / 20 * 60
    elif mode == "car":
        return distance_km / 40 * 60
    return 0

def generate_schedule(request: TravelRequest) -> TravelResponse:
    duration_text = request.duration
    match = re.search(r'(\d+)', duration_text)
    num_days = int(match.group(1)) if match else 3

    prompt = (
        f"You are a travel keyword recommendation expert. Based on the information below, print out the place keywords in your itinerary in JSON format.\n"
        f"Configure the {num_days} days schedule. Specify each date in the form Day 1 and Day 2.\n"
        f"Generate 7 to 8 place keywords for each date.\n"
        f"Just print out JSON without explanation, and create a type or feature (e.g., ocean view cafe, forest trail, etc.) that is not the name of the place.\n"
        f"Avoid abstract expressions, and organize them into the types of places you'll find in the real Jeju area.\n"
        f"If possible, recommend eco-friendly places such as plogging, Jeju Green Road, Udo, Gotjawal Forest, and renewable energy experiences first.\n"
        f"If you lack eco-friendly places, include general Jeju tourist maps.\n"
        f"Each date should consist of a distance (5 to 6 km) within an hour on foot.\n"
        f"Do not include public institutions.\n"
        f"Format example: {{\"scheduleList\": [{{\"day\": \"Day 1\", \"keywords\": [\"Oreum Tracking\", \"Local Restaurant\"]}}]}}\n"
        f"Input info: City={request.city}, Area={request.district}, Style={request.style}, Transport={', '.join(request.transport)}"
    )

    response = model.generate_content(prompt)
    try:
        content = response.text if hasattr(response, "text") else None
        content = re.sub(r"<(https?://[^>]+)>", r"\1", content)
        json_candidates = re.findall(r'{[\s\S]*}', content)
        if not json_candidates:
            raise ValueError("Gemini response is not a valid JSON format.")
        parsed = json.loads(json_candidates[0])

        result = {"scheduleList": []}
        fallback_keywords = ["Gotjawal", "Oreum", "Café", "Black Pig", "Tangerine Farm"]

        for i, day in enumerate(parsed.get("scheduleList", [])):
            keywords = day.get("keywords", [])[:10]
            places = []
            prev_place = None
            seen_coords = set()

            for keyword in keywords:
                place = get_place_from_kakao(keyword, request.district)
                if place:
                    coord = (place["lat"], place["lon"])
                    if coord in seen_coords:
                        continue 

                    if prev_place:
                        dist_km = haversine_distance(prev_place["lat"], prev_place["lon"], place["lat"], place["lon"])
                        car_time = estimate_travel_time_km(dist_km, "car")
                        if car_time > 40:
                            continue
                        place.update({
                            "walkTime": round(estimate_travel_time_km(dist_km, "walk")),
                            "bicycleTime": round(estimate_travel_time_km(dist_km, "bicycle")),
                            "publicTime": round(estimate_travel_time_km(dist_km, "public")),
                            "carTime": round(car_time)
                        })
                    else:
                        place.update({"walkTime": 0, "bicycleTime": 0, "publicTime": 0, "carTime": 0})

                    places.append({
                        "name": translate_place_name(place["name"]),
                        "imageUrl": place["imageUrl"],
                        "walkTime": place["walkTime"],
                        "bicycleTime": place["bicycleTime"],
                        "publicTime": place["publicTime"],
                        "carTime": place["carTime"],
                        "latitude": place["lat"],
                        "longitude": place["lon"]
                    })
                    prev_place = place
                    seen_coords.add(coord)

            if i < num_days - 1 and places:
                suite = get_place_from_kakao("lodging", request.district)
                if suite:
                    coord = (suite["lat"], suite["lon"])
                    if coord not in seen_coords:
                        dist_km = haversine_distance(places[-1]["latitude"], places[-1]["longitude"], suite["lat"], suite["lon"])
                        suite.update({
                            "walkTime": round(estimate_travel_time_km(dist_km, "walk")),
                            "bicycleTime": round(estimate_travel_time_km(dist_km, "bicycle")),
                            "publicTime": round(estimate_travel_time_km(dist_km, "public")),
                            "carTime": round(estimate_travel_time_km(dist_km, "car"))
                        })
                        places.append({
                            "name": translate_place_name(suite["name"]),
                            "imageUrl": suite["imageUrl"],
                            "walkTime": suite["walkTime"],
                            "bicycleTime": suite["bicycleTime"],
                            "publicTime": suite["publicTime"],
                            "carTime": suite["carTime"],
                            "latitude": suite["lat"],
                            "longitude": suite["lon"]
                        })
                        seen_coords.add(coord)

            result["scheduleList"].append({"day": day["day"], "places": places})

        return TravelResponse(**result)

    except Exception as e:
        print("❌Gemini response parsing failed:", e)
        raise ValueError("Gemini response is not a valid JSON format.")
