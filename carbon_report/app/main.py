from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.schema import CarbonEstimateRequest
from app.service import estimate_carbon


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ai/carbon/estimate")
def estimate_endpoint(request: CarbonEstimateRequest):
    return estimate_carbon(request)
