from pydantic import BaseModel
from uuid import UUID


class BandOut(BaseModel):
    id: UUID
    stream: str
    band: str
    designation: str

    class Config:
        from_attributes = True


class BandLookupOut(BaseModel):
    stream: str
    band: str
    designations: list[str]
