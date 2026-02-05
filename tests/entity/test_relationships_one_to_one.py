"""Tests for one-to-one relationships using Pydantic.

Pattern: Profile -> User (Profile has FK to User, Profile can access User)
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field, ConfigDict
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.fields import ReadonlyFieldDescriptor, readonly_field


metadata = MetaData()


class OneToOneBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


class User(OneToOneBase):
    model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))
    __sqlalchemy_params__ = {"__tablename__": "oto_user"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str


class Profile(OneToOneBase):
    model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))
    __sqlalchemy_params__ = {"__tablename__": "oto_profile"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    bio: str
    user_id: Annotated[UUID, mapped_column(ForeignKey("oto_user.id"))]

    user = readonly_field(
        User,
        SQLAlchemyField(
            name="user",
            attr=relationship(lambda: User.__sqlalchemy_type__),
        ),
    )


def test_one_to_one_forward_relationship():
    """Profile can access its User via readonly_field."""
    user = User(name="Alice")
    user_sa = user.to_sa_model()

    profile = Profile(bio="Software developer", user_id=user.id)
    profile_sa = profile.to_sa_model()
    profile_sa.user = user_sa

    restored_profile = Profile.from_sa_model(profile_sa)

    assert restored_profile.user.id == user.id
    assert restored_profile.user.name == user.name


def test_one_to_one_relationship_roundtrip():
    """Profile -> User relationship survives round-trip conversion."""
    user = User(name="Bob")
    user_sa = user.to_sa_model()

    profile = Profile(bio="Data scientist", user_id=user.id)
    profile_sa = profile.to_sa_model()
    profile_sa.user = user_sa

    # Full round-trip
    restored_profile = Profile.from_sa_model(profile_sa)

    assert restored_profile.id == profile.id
    assert restored_profile.bio == profile.bio
    assert restored_profile.user_id == user.id
    assert restored_profile.user.id == user.id
    assert restored_profile.user.name == user.name
