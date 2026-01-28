"""Tests for self-referential relationships.

Pattern: Employee -> manager (which is also an Employee)
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field
from sqlalchemy import MetaData, ForeignKey
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.fields import readonly_field


metadata = MetaData()


class SelfRefBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


class Employee(SelfRefBase):
    __sqlalchemy_params__ = {"__tablename__": "self_employee"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    manager_id: Annotated[UUID | None, mapped_column(ForeignKey("self_employee.id"))] = None

    manager = readonly_field(
        "Employee",  # Forward ref to self
        SQLAlchemyField(
            name="manager",
            attr=relationship(
                lambda: Employee.__sqlalchemy_type__,
                remote_side=lambda: Employee.__sqlalchemy_type__.id,
                back_populates="reports",
            ),
        ),
    )

    reports = readonly_field(
        list["Employee"],
        SQLAlchemyField(
            name="reports",
            attr=relationship(
                lambda: Employee.__sqlalchemy_type__,
                back_populates="manager",
            ),
        ),
    )


def test_self_referential_relationship():
    """Self-referential relationship (Employee -> manager) works correctly."""
    ceo = Employee(name="CEO")
    ceo_sa = ceo.to_sa_model()

    manager = Employee(name="Manager", manager_id=ceo.id)
    manager_sa = manager.to_sa_model()
    manager_sa.manager = ceo_sa

    employee = Employee(name="Employee", manager_id=manager.id)
    employee_sa = employee.to_sa_model()
    employee_sa.manager = manager_sa

    # Check the hierarchy
    assert employee_sa.manager is manager_sa
    assert manager_sa.manager is ceo_sa
    assert ceo_sa.manager is None

    # Check back_populates (reports)
    assert manager_sa in ceo_sa.reports
    assert employee_sa in manager_sa.reports

    # Conversion works
    restored_employee = Employee.from_sa_model(employee_sa)
    assert restored_employee.manager.name == "Manager"
    assert restored_employee.manager.manager.name == "CEO"
