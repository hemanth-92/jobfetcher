from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl

class Job(BaseModel):
    job_url: HttpUrl
    title: str
    company: Optional[str] = "Unknown"
    location: Optional[str] = "Unknown"
    date_posted: Optional[str] = None
    description: Optional[str] = ""
    site: Optional[str] = None
    source_query: Optional[str] = None
    source_location: Optional[str] = None
    is_remote: bool = False
    job_type: Optional[str] = None
    is_fortune_500: bool = False

    # Analysis fields
    est_min_years: Optional[int] = None
    est_max_years: Optional[int] = None

    class Config:
        coerce_numbers_to_str = True
