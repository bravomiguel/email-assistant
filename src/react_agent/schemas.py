from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Connection(BaseModel):
    person: str = Field(
        description="The full name of the person.", default=None
    )
    relation: str = Field(
        description="The relationship to the user, e.g. brother, colleague.",
        default=None,
    )
    email: Optional[str] = Field(
        description="The email address of the person.", default=None
    )


# user profile schema
class Profile(BaseModel):
    """This is the profile of the user you are chatting with."""

    name: Optional[str] = Field(description="The name of the user.", default=None)
    location: Optional[str] = Field(
        description="Where the user lives. Include place and state name, e.g. Austin, TX",
        default=None,
    )
    job: Optional[str] = Field(
        description="The user's job. Include company name and title if possible, e.g. Software Engineer at Google",
        default=None,
    )
    connections: List[Connection] = Field(
        description="List of people the user knows, with their name, relationship, and email address, e.g. Miguel Bravo, brother, miguelbravo@example.com",
        default_factory=list,
    )
