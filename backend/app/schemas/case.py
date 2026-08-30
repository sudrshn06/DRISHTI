from pydantic import BaseModel, Field

class CaseExportRequest(BaseModel):
    """
    Schema for customized complaint drafts and notes submitted for ZIP evidence compilation.
    """
    complaint_draft: str = Field(..., description="Factual complaint/enforcement text edited by the officer")
    officer_notes: str = Field("", description="Custom inspector remarks or context notes")
