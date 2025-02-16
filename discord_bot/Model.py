from typing import Dict, List

from pydantic import BaseModel


class ErrorModel(BaseModel):
    error: str

class JobPosting(BaseModel):
    title: str
    company: str
    url: str

class JobResponse(BaseModel):
    searches: Dict[str, Dict[str, Dict[str, JobPosting]]]