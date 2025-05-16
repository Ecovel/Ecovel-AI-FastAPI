from app.schema import CarbonEstimateRequest, CarbonEstimateResponse
from app.converter import calculate_eco_score

def estimate_carbon(data: CarbonEstimateRequest) -> CarbonEstimateResponse:
    vehicle_factor = 0.21
    public_factor = 0.12
    bicycle_factor = 0.0
    walk_factor = 0.0

    expected = 0.0
    actual = 0.0
    details = []

    for schedule in data.schedules:
        day_expected = 0.0
        day_actual = 0.0
        for place in schedule.places:
            total_time = place.walkTime + place.bicycleTime + place.publicTime + place.carTime
            day_expected += total_time * vehicle_factor
            day_actual += (
                place.walkTime * walk_factor +
                place.bicycleTime * bicycle_factor +
                place.publicTime * public_factor +
                place.carTime * vehicle_factor
            )
        details.append({
            "day": schedule.day,
            "transportMode": "bus",  # 실제로는 동적 분석 가능
            "vehicleCarbon": round(day_expected, 1),
            "actualCarbon": round(day_actual, 1)
        })
        expected += day_expected
        actual += day_actual

    reduced = expected - actual
    score = calculate_eco_score(reduced)

    return CarbonEstimateResponse(
        reportId=None,
        planId=data.planId,
        expectedCarbon=round(expected, 1),
        actualCarbon=round(actual, 1),
        reducedCarbon=round(reduced, 1),
        ecoScore=score,
        details=details
    )
