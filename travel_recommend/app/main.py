from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import TravelRequest, TravelResponse
from app.service import generate_schedule

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ai/recommend", response_model=TravelResponse)
def recommend_travel(request: TravelRequest):
    return generate_schedule(request)
