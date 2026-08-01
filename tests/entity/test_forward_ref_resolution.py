from typing import Annotated, Any, ClassVar, ForwardRef
from uuid import UUID, uuid4

import pytest
from pydantic import Field
from sqlalchemy import MetaData
from sqlalchemy.orm import mapped_column

from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.field_definitions import (
    UnresolvableForwardRefError,
    canonicalise_typeform,
)


class BaseTestEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


class ShadowedForwardRef(BaseTestEntity):
    """A class attribute shadows a forward ref's name with a string of the same value.

    Resolving ``ForwardRef("Widget")`` against this class yields the string
    ``"Widget"`` again, so resolution makes no progress.
    """

    __sqlalchemy_params__ = {"__tablename__": "shadowed_forward_ref"}

    Widget: ClassVar[str] = "Widget"

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)


def test_non_progressing_forward_ref_raises_rather_than_recursing():
    """A forward ref that resolves to itself is reported instead of blowing the stack."""
    # Built through an Any-typed alias so the type checker reads this as a
    # runtime value rather than a type expression.
    container: Any = list
    typeform = container[ForwardRef("Widget")]

    with pytest.raises(UnresolvableForwardRefError, match="Widget"):
        canonicalise_typeform(ShadowedForwardRef, typeform).resolve()
