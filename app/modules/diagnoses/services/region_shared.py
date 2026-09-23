from __future__ import annotations

from app.core.exceptions import ValidationError
from app.modules.diagnoses.models import Diagnosis
from app.modules.diagnoses.repositories.interfaces import DiagnosisRegionRepository
from app.modules.diagnoses.schemas import DiagnosisRegionPayload


def validate_region_payload(payload: DiagnosisRegionPayload) -> None:
    values = {"x": payload.x, "y": payload.y, "width": payload.width, "height": payload.height}
    if any(value < 0 or value > 100 for value in values.values()):
        raise ValidationError("As coordenadas da area devem estar entre 0 e 100.")
    if payload.width <= 0 or payload.height <= 0:
        raise ValidationError("A area selecionada deve ter largura e altura validas.")
    if payload.x + payload.width > 100 or payload.y + payload.height > 100:
        raise ValidationError("A area selecionada deve ficar dentro da imagem do ECG.")


def sync_legacy_region_fields(
    diagnosis_region_repository: DiagnosisRegionRepository, diagnosis: Diagnosis
) -> None:
    regions = diagnosis_region_repository.list_for_diagnosis(diagnosis.id)
    first_region = regions[0] if regions else None

    if first_region:
        diagnosis.region_x = first_region.x
        diagnosis.region_y = first_region.y
        diagnosis.region_width = first_region.width
        diagnosis.region_height = first_region.height
    else:
        diagnosis.region_x = None
        diagnosis.region_y = None
        diagnosis.region_width = None
        diagnosis.region_height = None
