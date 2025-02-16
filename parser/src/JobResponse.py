from typing import Dict

from pydantic import BaseModel


class JobPosting(BaseModel):
    title: str
    company: str
    url: str

class JobResponse(BaseModel):
    searches: Dict[str, Dict[str, Dict[str, JobPosting]]]