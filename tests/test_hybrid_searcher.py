from unittest.mock import MagicMock, patch

from pipelines.sap.preprocessor import InputPreprocessor, ProcessedQuery


def test_preprocess_extracts_tcode():
    preprocessor = InputPreprocessor()
    result = preprocessor.preprocess("SM21에서 오류가 발생했습니다")
    assert "SM21" in result.tcodes
    assert "SM21" in result.normalized


def test_preprocess_extracts_error_code():
    preprocessor = InputPreprocessor()
    result = preprocessor.preprocess("BRAIN000 오류 코드 해결 방법")
    assert result.error_codes  # 오류코드 추출 확인


def test_preprocess_plain_query():
    preprocessor = InputPreprocessor()
    result = preprocessor.preprocess("SAP 인보이스 처리 방법")
    assert result.original == "SAP 인보이스 처리 방법"
    assert result.normalized.strip()
