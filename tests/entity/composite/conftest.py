"""Shared fixtures and entity definitions for composite-field tests."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, Integer, MetaData, String
from sqlalchemy.orm import Mapped, composite, mapped_column

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel


class Money(BaseModel):
    """Composite value class. Implements SA's composite protocol via
    ``__composite_values__``; Pydantic gives us validation, equality
    and an immutable shape. The positional ``__init__`` overload
    matches the call SA's composite descriptor makes when reading a
    row back from the DB (``Money(amount, currency)``)."""

    model_config = ConfigDict(frozen=True)

    amount: int
    currency: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        if args and not kwargs:
            amount, currency = args
            super().__init__(amount=amount, currency=currency)
        else:
            super().__init__(**kwargs)

    def __composite_values__(self) -> tuple[int, str]:
        return (self.amount, self.currency)


class _MoneyDescriptor(Mapped):
    """Class-attribute marker that injects two SA columns + a
    ``composite()`` at class-build time. Subclasses ``Mapped`` so
    SQLCrucible recognises it as a column-bearing attribute and emits
    the matching ``Mapped[Money]`` annotation."""

    def __set_name__(self, owner: type, name: str) -> None:
        amount_col_name = f"{name}_amount"
        currency_col_name = f"{name}_currency"
        setattr(owner, amount_col_name, Column(Integer, nullable=True))
        setattr(owner, currency_col_name, Column(String, nullable=True))
        setattr(owner, name, composite(Money, amount_col_name, currency_col_name))


def money_composite() -> SQLAlchemyField:
    return SQLAlchemyField(attr=_MoneyDescriptor())


class _Base(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}


class Product(_Base):
    __sqlalchemy_params__ = {"__tablename__": "product"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    price: Annotated[Money, money_composite()]


class NullableProduct(_Base):
    __sqlalchemy_params__ = {"__tablename__": "nullable_product"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    price: Annotated[Money | None, money_composite()] = None
