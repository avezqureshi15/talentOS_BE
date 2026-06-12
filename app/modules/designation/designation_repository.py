from sqlalchemy.orm import Session

from app.modules.designation.designation_model import Band, Designation, KpiDefinition


class DesignationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_names(self) -> list[str]:
        rows = self.db.query(Designation.name).distinct().order_by(Designation.name).all()
        return [row[0] for row in rows]

    def get_designation_with_details(self, name: str) -> dict | None:
        results = (
            self.db.query(
                Designation.id,
                Designation.name,
                Designation.department,
                Band.id.label("band_id"),
                Band.name.label("band_name"),
                KpiDefinition.id.label("kpi_id"),
                KpiDefinition.kpi_name,
                KpiDefinition.weightage,
                KpiDefinition.active,
            )
            .join(Band, Designation.band_id == Band.id)
            .outerjoin(KpiDefinition, Designation.name == KpiDefinition.designation)
            .filter(Designation.name == name)
            .all()
        )

        if not results:
            return None

        designation_data = {
            "id": results[0].id,
            "name": results[0].name,
            "department": results[0].department,
        }
        band_data = {
            "id": results[0].band_id,
            "name": results[0].band_name,
        }
        kpis_data = []
        seen_kpi_ids: set[int] = set()
        for row in results:
            if row.kpi_id is not None and row.kpi_id not in seen_kpi_ids:
                seen_kpi_ids.add(row.kpi_id)
                kpis_data.append({
                    "id": row.kpi_id,
                    "kpi_name": row.kpi_name,
                    "weightage": row.weightage,
                    "active": row.active,
                })

        return {
            "designation": designation_data,
            "band": band_data,
            "kpis": kpis_data,
        }
