import re
from dataclasses import dataclass, field

_TCODE_RE = re.compile(r"\b([A-Z]{2,4}[0-9]{1,3}|[A-Z]{3,6})\b")
_ERROR_RE = re.compile(r"\b([A-Z]{2,4}[0-9]{3,4})\b")
_NOTE_RE = re.compile(r"(?:SAP\s*)?[Nn]ote\s*#?\s*(\d{6,7})")


@dataclass
class ProcessedQuery:
    original: str
    normalized: str
    tcodes: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    sap_notes: list[str] = field(default_factory=list)


class InputPreprocessor:
    def preprocess(self, query: str) -> ProcessedQuery:
        upper = query.upper()
        tcodes = list(set(_TCODE_RE.findall(upper)))
        error_codes = list(set(_ERROR_RE.findall(upper)))
        sap_notes = _NOTE_RE.findall(query)

        normalized = query.strip()
        if error_codes:
            normalized = f"[오류코드: {', '.join(error_codes)}] {normalized}"
        if tcodes:
            normalized = f"[T-code: {', '.join(tcodes)}] {normalized}"

        return ProcessedQuery(
            original=query,
            normalized=normalized,
            tcodes=tcodes,
            error_codes=error_codes,
            sap_notes=sap_notes,
        )
