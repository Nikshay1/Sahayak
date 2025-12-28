from pydantic import BaseModel
from typing import List

class Intent(BaseModel):
    intent_type: str
    items: List[str]
    quantity: int
    confidence_score: float
