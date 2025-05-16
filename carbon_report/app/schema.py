from typing import List
from pydantic import BaseModel
from typing import Optional

class Place(BaseModel):
    name: str
    walkTime: int
    bicycleTime: int
    publicTime: int
    carTime: int

class Schedule(BaseModel):
    day: str
    places: List[Place]

class CarbonEstimateRequest(BaseModel):
    planId: int
    schedules: List[Schedule]

class DayCarbonDetail(BaseModel):
    day: str
    transportMode: str
    vehicleCarbon: float
    actualCarbon: float

class CarbonEstimateResponse(BaseModel):
    reportId: Optional[int]
    planId: int
    expectedCarbon: float
    actualCarbon: float
    reducedCarbon: float
    ecoScore: int
    details: List[DayCarbonDetail]
