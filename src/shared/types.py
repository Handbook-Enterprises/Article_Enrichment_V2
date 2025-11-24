from typing import List, Optional, Literal
from pydantic import BaseModel, HttpUrl, Field, field_validator

# Represents a location in the document where a media item (image or video) should be inserted.
class Place(BaseModel):
    section_heading: Optional[str] = None
    paragraph_index: Optional[int] = None
    sentence_index: Optional[int] = None
    after_heading: bool = True

# Represents a media item (image or video) to be inserted in the document.
class MediaSelection(BaseModel):
    id: int
    type: Literal["image", "video"]
    url: str
    alt: str = Field(min_length=1, max_length=125)
    place: Place

    @field_validator("alt")
    @classmethod
    def no_image_of_prefix(cls, v: str):
        bad = v.strip().lower()
        if bad.startswith("image of") or bad.startswith("picture of"):
            raise ValueError("Alt text must not start with 'Image of' or 'Picture of'")
        return v

# Represents a link to be inserted in the document.
class LinkSelection(BaseModel):
    id: int
    url: str
    anchor: str
    keyword: str
    place: Place

# Represents a collection of selections to be inserted in the document.
class Selection(BaseModel):
    hero: MediaSelection
    context_item: MediaSelection
    links: List[LinkSelection]

    @field_validator("links")
    @classmethod
    def must_have_two_links(cls, v: List[LinkSelection]):
        if len(v) != 2:
            raise ValueError("Exactly two links are required")
        return v