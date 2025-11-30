from pydantic import BaseModel
from typing import List, Optional


class UserImageItem(BaseModel):
    image_type: str            # "BODY" | "FACE" | ...
    image_url: str
    created_at: str            # ISO datetime string


class UserImagesResponse(BaseModel):
    user_id: int
    images: List[UserImageItem]
    
class OnboardingDTO(BaseModel):
    styles: List[str] = []
    preferred_colors: List[str] = []
    preferred_fits: List[str] = []

class AccountInfoDTO(BaseModel):
    id: int
    username: str
    gender: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    onboarding: OnboardingDTO