from app.intent import parse_intent
from app.wallet import debit
from app.pharmacy import place_order
from app.tts import speak

USER_ID = 1

def handle(text: str):
    intent = parse_intent(text)

    if intent.confidence_score < 0.85:
        speak("I did not understand. Please call your caregiver.")
        return

    if intent.intent_type == "ORDER_MEDICINE":
        order = place_order(intent.items[0], intent.quantity)

        ok, err = debit(USER_ID, order["price"])
        if not ok:
            speak(f"Sorry. {err}")
            return

        speak(
            f"I have ordered {intent.items[0]}. "
            f"It cost {order['price']} rupees. "
            f"It will arrive by evening."
        )
