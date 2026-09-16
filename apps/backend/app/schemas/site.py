from pydantic import BaseModel, ConfigDict


class SiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    site_id: str
    site_name: str
    site_type: str
    location: str | None
    capacity_kw: float | None
    status: str | None
