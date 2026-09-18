from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: int
    alert_id: int
    action: str
    explanation: str
    rule_reference: str
    created_at: datetime
