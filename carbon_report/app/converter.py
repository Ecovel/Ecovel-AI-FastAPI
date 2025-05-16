def carbon_to_tree_equivalent(carbon_kg: float) -> str:
    if carbon_kg < 30:
        return "Equivalent to planting 3–5 trees 🌲"
    elif carbon_kg < 60:
        return "Equivalent to planting 6–9 trees 🌲"
    elif carbon_kg < 100:
        return "Equivalent to planting 10–15 trees 🌲"
    else:
        return "Equivalent to creating a small forest 🌳"

def calculate_eco_score(carbon_saved: float) -> int:
    if carbon_saved >= 100:
        return 10
    elif carbon_saved >= 75:
        return 8
    elif carbon_saved >= 50:
        return 6
    elif carbon_saved >= 30:
        return 4
    else:
        return 2
