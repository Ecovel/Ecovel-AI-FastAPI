from fastapi import FastAPI
from app.schemas import TravelRequest, TravelResponse
from app.service import generate_schedule

app = FastAPI()


@app.post("/ai/recommend", response_model=TravelResponse)
def recommend_travel(request: TravelRequest):
    return generate_schedule(request)
