from app.services.zone_service import get_zone_by_id


def build_recommendations_for_zone(zone_id: str) -> dict | None:
    zone = get_zone_by_id(zone_id, include_risk=True)

    if zone is None:
        return None

    recommendations = []

    if zone["heat_risk"] > 66:
        recommendations.extend([
            "Creșterea suprafeței de spații verzi în zonele dense.",
            "Plantarea de arbori și amenajarea unor zone de umbrire.",
            "Monitorizarea temperaturilor în perioadele de caniculă."
        ])

    if zone["flood_risk"] > 66:
        recommendations.extend([
            "Curățarea rigolelor și verificarea sistemului de canalizare.",
            "Creșterea suprafețelor permeabile.",
            "Monitorizarea zonelor joase în timpul ploilor abundente."
        ])

    if zone["pollution_risk"] > 66:
        recommendations.extend([
            "Reducerea traficului în orele de vârf.",
            "Încurajarea transportului public și a mobilității alternative.",
            "Monitorizarea calității aerului în punctele aglomerate."
        ])

    if zone["global_risk"] > 66:
        recommendations.append(
            "Prioritizarea zonei pentru analiză suplimentară și intervenții locale."
        )

    if not recommendations:
        recommendations.append(
            "Zona nu prezintă risc ridicat în modelul curent; se recomandă monitorizare periodică."
        )

    return {
        "zone_id": zone["zone_id"],
        "zone_name": zone["name"],
        "global_risk": zone["global_risk"],
        "global_label": zone["global_label"],
        "recommendations": recommendations
    }