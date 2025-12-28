from app.models import Intent

def parse_intent(text: str) -> Intent:
    text = text.lower()

    if "medicine" in text or "tablet" in text:
        return Intent(
            intent_type="ORDER_MEDICINE",
            items=["Shelcal 500"],
            quantity=1,
            confidence_score=0.92
        )

    return Intent(
        intent_type="UNKNOWN",
        items=[],
        quantity=0,
        confidence_score=0.3
    )
