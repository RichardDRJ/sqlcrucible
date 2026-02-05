"""Tests for association_proxy support on SQLCrucible entities."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.orm import Session

from sqlcrucible.entity.sa_type import SAType

from .conftest import Department, EmployeeWithProxy


def test_association_proxy_exists_on_satype():
    """association_proxy is available on the generated SAType."""
    sa_type = SAType[EmployeeWithProxy]
    assert "department_name" in sa_type.__dict__
    assert isinstance(sa_type.__dict__["department_name"], AssociationProxy)


def test_association_proxy_access(association_proxy_engine):
    """association_proxy provides access to related object attributes."""
    dept_sa = SAType[Department]
    emp_sa = SAType[EmployeeWithProxy]

    with Session(association_proxy_engine) as session:
        dept = dept_sa(id=uuid4(), name="Engineering")
        session.add(dept)
        session.flush()

        emp = emp_sa(id=uuid4(), name="Alice", department_id=dept.id)
        session.add(emp)
        session.commit()

        loaded_emp = session.scalar(select(emp_sa))
        assert loaded_emp is not None
        assert loaded_emp.department_name == "Engineering"


def test_association_proxy_in_filter(association_proxy_engine):
    """association_proxy can be used in filter queries."""
    dept_sa = SAType[Department]
    emp_sa = SAType[EmployeeWithProxy]

    with Session(association_proxy_engine) as session:
        eng_dept = dept_sa(id=uuid4(), name="Engineering")
        sales_dept = dept_sa(id=uuid4(), name="Sales")
        session.add_all([eng_dept, sales_dept])
        session.flush()

        alice = emp_sa(id=uuid4(), name="Alice", department_id=eng_dept.id)
        bob = emp_sa(id=uuid4(), name="Bob", department_id=sales_dept.id)
        session.add_all([alice, bob])
        session.commit()

        engineers = session.scalars(
            select(emp_sa).where(emp_sa.department_name == "Engineering")
        ).all()

        assert len(engineers) == 1
        assert engineers[0].name == "Alice"
