"""Tests for many-to-many relationships using Pydantic.

Pattern: Student -> Courses (via association table)
Testing the Student side of the relationship with forward references.
"""

from uuid import uuid4, UUID
from typing import Annotated

from pydantic import Field
from sqlalchemy import MetaData, ForeignKey, Table, Column
from sqlalchemy.orm import mapped_column, relationship

from sqlcrucible.entity.annotations import SQLAlchemyField
from sqlcrucible.entity.core import SQLCrucibleBaseModel
from sqlcrucible.entity.fields import readonly_field


metadata = MetaData()


class ManyToManyBase(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": metadata}


# Association table for many-to-many relationship
student_course_table = Table(
    "mtm_student_course",
    metadata,
    Column("student_id", ForeignKey("mtm_student.id"), primary_key=True),
    Column("course_id", ForeignKey("mtm_course.id"), primary_key=True),
)


class Student(ManyToManyBase):
    __sqlalchemy_params__ = {"__tablename__": "mtm_student"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

    # Forward reference to list of Courses (defined below)
    courses = readonly_field(
        list["Course"],
        SQLAlchemyField(
            name="courses",
            attr=relationship(
                lambda: Course.__sqlalchemy_type__,
                secondary=student_course_table,
            ),
        ),
    )


class Course(ManyToManyBase):
    __sqlalchemy_params__ = {"__tablename__": "mtm_course"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: str


def test_many_to_many_student_to_courses():
    """Student can access their list of Courses."""
    student = Student(name="Alice")
    student_sa = student.to_sa_model()

    course1 = Course(title="Mathematics")
    course2 = Course(title="Physics")
    course1_sa = course1.to_sa_model()
    course2_sa = course2.to_sa_model()

    student_sa.courses = [course1_sa, course2_sa]

    restored_student = Student.from_sa_model(student_sa)

    assert len(restored_student.courses) == 2
    course_titles = {c.title for c in restored_student.courses}
    assert course_titles == {"Mathematics", "Physics"}


def test_many_to_many_empty_relationship():
    """Student with no courses returns empty list."""
    student = Student(name="New Student")
    student_sa = student.to_sa_model()
    student_sa.courses = []

    restored_student = Student.from_sa_model(student_sa)

    assert restored_student.courses == []


def test_many_to_many_roundtrip():
    """Many-to-many relationship survives round-trip conversion."""
    student = Student(name="Frank")
    student_sa = student.to_sa_model()

    course1 = Course(title="Art")
    course2 = Course(title="Music")
    course1_sa = course1.to_sa_model()
    course2_sa = course2.to_sa_model()

    student_sa.courses = [course1_sa, course2_sa]

    restored_student = Student.from_sa_model(student_sa)

    assert restored_student.id == student.id
    assert restored_student.name == student.name
    assert len(restored_student.courses) == 2
    course_titles = {c.title for c in restored_student.courses}
    assert course_titles == {"Art", "Music"}
