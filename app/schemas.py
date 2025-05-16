from pydantic import BaseModel
from typing import List


class TravelRequest(BaseModel):
    city: str
    district: str
    duration: str
    style: str
    transport: List[str]


class Place(BaseModel):
    name: str
    imageUrl: str
    walkTime: int
    bicycleTime: int
    publicTime: int
    carTime: int


class DaySchedule(BaseModel):
    day: str
    places: List[Place]


class TravelResponse(BaseModel):
    scheduleList: List[DaySchedule]
