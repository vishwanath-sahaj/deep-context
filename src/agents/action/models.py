from pydantic import BaseModel, Field
from typing import Optional

class UIElement(BaseModel):
    element_name: str = Field(description="Name or selector of the element, e.g., 'button1', 'text1'")
    action: str = Field(description="Action to perform, e.g., 'click', 'fill', 'hover'")
    next_element: Optional['UIElement'] = None
