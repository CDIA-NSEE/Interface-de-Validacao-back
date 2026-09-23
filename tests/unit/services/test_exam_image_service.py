from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError
from app.services.exam_image_service import ExamImageService
from app.services.storage.metadata_blob_image_storage import MetadataBlobImageStorage
from tests.unit.services.conftest import make_exam


@pytest.fixture()
def service(exam_repository, fake_metadata_repository):
    storage = MetadataBlobImageStorage(fake_metadata_repository)
    return ExamImageService(exam_repository, storage)


def test_get_image_not_found_for_missing_exam(service):
    with pytest.raises(NotFoundError):
        service.get_image(999)


def test_get_image_returns_content_when_blob_present(session, service, fake_metadata_repository):
    exam = make_exam(session, metadata_id=1)
    fake_metadata_repository._images[1] = {"content": b"bytes", "media_type": "image/png"}

    result = service.get_image(exam.id)

    assert result == {"kind": "content", "content": b"bytes", "media_type": "image/png"}


def test_get_image_falls_back_to_redirect_url(session, service):
    exam = make_exam(session, metadata_id=None, image_url="/custom.svg")

    result = service.get_image(exam.id)

    assert result == {"kind": "redirect", "url": "/custom.svg"}


def test_get_image_falls_back_to_default_sample_when_no_url(session, service):
    exam = make_exam(session, metadata_id=None, image_url="")

    result = service.get_image(exam.id)

    assert result == {"kind": "redirect", "url": "/sample-ecg.svg"}
