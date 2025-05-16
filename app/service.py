from google.generativeai import configure, GenerativeModel
from app.config import GEMINI_API_KEY
from app.schemas import TravelRequest, TravelResponse
from pydantic import ValidationError
from fastapi.responses import JSONResponse
from pprint import pprint
import json
import re
import requests
import urllib.parse

# Gemini 설정
configure(api_key=GEMINI_API_KEY)
model = GenerativeModel("gemini-1.5-flash")

def is_valid_image_url(url: str) -> bool:
    try:
        r = requests.head(url, timeout=3)
        content_type = r.headers.get("Content-Type", "")
        return r.status_code == 200 and "image" in content_type
    except:
        return False

def search_image_url(query: str) -> str:
    try:
        headers = { "User-Agent": "Mozilla/5.0" }
        url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&qft=+filterui:imagesize-large&form=IRFLTR"
        res = requests.get(url, headers=headers, timeout=5)

        # 🔍 다양한 패턴으로 이미지 URL 추출 시도
        matches = (
            re.findall(r'murl\\\":\\\"(https:[^\\\"]+)', res.text) or
            re.findall(r'imgurl=(https[^&]+)', res.text) or
            re.findall(r'src=\"(https://[^"]+\.jpg)\"', res.text)
        )

        for img_url in matches:
            if is_valid_image_url(img_url):
                return img_url

    except Exception as e:
        print(f"🔍 이미지 검색 실패: {query} - {e}")
    return ""


def generate_schedule(request: TravelRequest):
    prompt = (
    f"당신은 친환경 여행 전문가입니다. 아래 정보를 바탕으로 3일 여행 일정을 JSON 형식으로 출력하세요.\n"
    f"조건은 다음과 같습니다:\n\n"
    f"1. 각 장소는 name, imageUrl, walkTime, bicycleTime, publicTime, carTime, placeType을 포함해야 합니다.\n"
    f"2. placeType은 반드시 'tourist', 'cafe', 'accommodation' 중 하나여야 합니다.\n"
    f"3. 각 날짜의 중간에는 카페(cafe)를 한 곳 포함하고, 마지막에는 숙소(accommodation)를 반드시 포함하세요.\n"
    f"4. imageUrl은 실제 인터넷에 존재하는 이미지 링크여야 하며, 가짜 주소나 404 페이지가 아닌 실제 이미지 파일이어야 합니다.\n"
    f"5. JSON 외의 텍스트는 포함하지 마세요. '{' 로 시작하고 '}' 로 끝나는 유효한 JSON으로만 응답하세요.\n\n"
    f"[입력 정보]\n"
    f"- 도시: {request.city} / 지역: {request.district}\n"
    f"- 여행 기간: {request.duration}\n"
    f"- 여행 스타일: {request.style}\n"
    f"- 교통수단: {', '.join(request.transport)}\n"
)



    response = model.generate_content(prompt)

    try:
        content = None
        if hasattr(response, "text") and response.text:
            content = response.text
        elif hasattr(response, "candidates"):
            for c in response.candidates:
                if hasattr(c, "content") and hasattr(c.content, "parts"):
                    for part in c.content.parts:
                        if hasattr(part, "text"):
                            content = part.text
                            break

        print("\n🧠 Gemini 응답 원문:\n", content or "[빈 응답]")

        if not content or not content.strip():
            raise ValueError("Gemini 응답이 비어 있습니다.")

        content = re.sub(r"<(https?://[^>]+)>", r"\1", content)
        json_candidates = re.findall(r'{\s*\"scheduleList\".*}', content, re.DOTALL)
        if not json_candidates:
            raise ValueError("Gemini 응답에서 JSON 구조를 찾을 수 없습니다.")

        parsed_dict = json.loads(json_candidates[0])

        # imageUrl 유효성 검사 및 대체
        for day in parsed_dict.get("scheduleList", []):
            for place in day.get("places", []):
                url = place.get("imageUrl")
                if not url or not is_valid_image_url(url):
                    query = place.get("name", "") + " 제주 관광지"
                    real_url = search_image_url(query)
                    place["imageUrl"] = real_url
                    print(f"🔄 이미지 URL 보완됨: {place['name']} → {real_url}")

        try:
            travel_resp = TravelResponse(**parsed_dict)
        except ValidationError as ve:
            print("❌ TravelResponse 검증 실패:")
            pprint(ve.errors())
            raise

        return JSONResponse(content=travel_resp.dict())

    except Exception as e:
        print("❌ Gemini 응답 파싱 실패:", e)
        raise ValueError("Gemini 응답이 유효한 JSON 형식이 아닙니다.")
