from pydantic import BaseModel, ConfigDict


class DesignationResponse(BaseModel):
    id: int
    name: str
    department: str


class BandInfoResponse(BaseModel):
    id: int
    name: str


class KpiResponse(BaseModel):
    id: int
    kpi_name: str
    weightage: int
    active: bool


class DesignationDetailResponse(BaseModel):
    designation: DesignationResponse
    band: BandInfoResponse
    kpis: list[KpiResponse]

    model_config = ConfigDict(from_attributes=True)
