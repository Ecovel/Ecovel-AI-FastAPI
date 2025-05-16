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
    "제주 그린로드 산책로": "제주 그린로드",
    "플로깅 가능 해변": "이호테우해변",
    "곶자왈 숲길 트래킹 코스": "곶자왈",
    "제주 전통 가옥 체험": "제주민속촌",
    "우도 등대 전망대": "우도등대공원",
    "바다 전망 카페": "해변 카페",
    "감귤농장 체험": "감귤체험농장",
    "제주 재생에너지 테마파크": "에너지미래관",
    "바다 조망 카페": "해변 카페",
    "우도 해변 카페 (친환경 인증)": "우도 카페",
    "제주플로우 프로그램 참여 가능한 농장": "제주농촌체험마을"
}

def get_google_place_image(place_name: str, api_key: str) -> str:
    query = f"제주 {place_name}"
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
        f"당신은 여행 키워드 추천 전문가입니다. 아래 정보를 바탕으로 여행 일정의 장소 키워드를 JSON 형식으로 출력하세요.\n"
        f"{num_days}일 일정으로 구성하세요. 각 날짜는 Day 1, Day 2 형태로 명시하세요.\n"
        f"각 날짜마다 7~8개의 장소 키워드를 생성하세요.\n"
        f"설명 없이 JSON만 출력하고, 장소 이름이 아닌 유형이나 특징(예: 바다 전망 카페, 숲속 산책로 등)을 생성하세요.\n"
        f"추상적인 표현은 피하고, 실제 제주 지역에서 찾을 수 있을 법한 장소 유형으로 구성하세요.\n"
        f"가능하면 플로깅, 제주 그린로드, 우도, 곶자왈 숲, 재생에너지 체험 등 친환경적인 장소를 우선 추천하세요.\n"
        f"친환경 장소가 부족하면 일반적인 제주 관광지도 포함하세요.\n"
        f"각 날짜는 도보 기준 1시간 이내 거리(5~6km) 장소로 구성하세요.\n"
        f"공공기관은 포함하지 마세요.\n"
        f"형식 예시: {{\"scheduleList\": [{{\"day\": \"Day 1\", \"keywords\": [\"오름 트래킹\", \"현지 식당\"]}}]}}\n"
        f"입력 정보: 도시={request.city}, 지역={request.district}, 스타일={request.style}, 교통수단={', '.join(request.transport)}"
    )

    response = model.generate_content(prompt)
    try:
        content = response.text if hasattr(response, "text") else None
        content = re.sub(r"<(https?://[^>]+)>", r"\1", content)
        json_candidates = re.findall(r'{[\s\S]*}', content)
        if not json_candidates:
            raise ValueError("Gemini 응답이 유효한 JSON 형식이 아닙니다.")
        parsed = json.loads(json_candidates[0])

        result = {"scheduleList": []}
        fallback_keywords = ["곶자왈", "오름", "카페", "흑돼지", "감귤농장"]

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
                        continue  # ✅ 동일 장소 완전 제외

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
                suite = get_place_from_kakao("숙소", request.district)
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
        print("❌ Gemini 응답 파싱 실패:", e)
        raise ValueError("Gemini 응답이 유효한 JSON 형식이 아닙니다.")
