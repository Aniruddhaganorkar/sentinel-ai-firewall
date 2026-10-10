from fastapi import APIRouter, File, Form, UploadFile

from app.firewall.pipeline import scan_content
from app.models import ScanRequest, ScanResult, SourceType

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("", response_model=ScanResult)
def scan(req: ScanRequest) -> ScanResult:
    return scan_content(req)


@router.post("/upload", response_model=ScanResult)
async def scan_upload(
    user_input: str = Form(...),
    source: SourceType = Form(SourceType.pdf),
    file: UploadFile = File(...),
) -> ScanResult:
    data = await file.read()
    text = ""
    if source != SourceType.pdf:
        text = data.decode("utf-8", errors="replace")
    req = ScanRequest(user_input=user_input, untrusted_content=text, source=source)
    return scan_content(req, untrusted_binary=data if source == SourceType.pdf else None)
