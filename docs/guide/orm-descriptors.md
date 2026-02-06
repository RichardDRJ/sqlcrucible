# ORM Descriptors

SQLCrucible supports SQLAlchemy ORM descriptors like `hybrid_property` and `association_proxy`. These provide computed attributes that work both in Python and in SQL queries.

## hybrid_property

A `hybrid_property` defines a computed attribute that can be used in Python code and in SQL queries (WHERE, ORDER BY, etc.).

### Basic Usage

Define the function **outside** the class body and use `readonly_field` to mark it as a computed attribute:

```python
from typing import Annotated
from uuid import UUID, uuid4
from pydantic import Field
from sqlalchemy.orm import mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible import readonly_field

def _full_name(self) -> str:
    return f"{self.first_name} {self.last_name}"

class Person(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "person"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]

    # Annotated syntax: put hybrid_property in the annotation
    full_name: Annotated[str, hybrid_property(_full_name)] = readonly_field(str)
```

### Using in Queries

The `hybrid_property` is available on the SQLAlchemy model and can be used in queries:

```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlcrucible import SAType

with Session(engine) as session:
    # Filter by hybrid property
    people = session.scalars(
        select(SAType[Person]).where(SAType[Person].full_name == "John Doe")
    ).all()

    # Order by hybrid property
    sorted_people = session.scalars(
        select(SAType[Person]).order_by(SAType[Person].full_name)
    ).all()
```

### Alternative Syntax

You can also pass the descriptor directly to `readonly_field` instead of using `Annotated`:

```python
class Person(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "person"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]

    # Pass descriptor directly - no annotation needed
    full_name = readonly_field(str, hybrid_property(_full_name))
```

For advanced cases (e.g., custom mapped name), you can pass both a descriptor and `SQLAlchemyField`:

```python
from sqlcrucible import SQLAlchemyField

# Order doesn't matter - both are equivalent
full_name = readonly_field(str, hybrid_property(_full_name), SQLAlchemyField(name="custom_name"))
full_name = readonly_field(str, SQLAlchemyField(name="custom_name"), hybrid_property(_full_name))
```

### Writable hybrid_property

For hybrid properties with setters, omit `readonly_field` so the field participates in conversion:

```python
def _get_full_name(self) -> str:
    return f"{self.first_name} {self.last_name}"

def _set_full_name(self, value: str) -> None:
    parts = value.split(" ", 1)
    self.first_name = parts[0]
    self.last_name = parts[1] if len(parts) > 1 else ""

_full_name_hybrid = hybrid_property(_get_full_name).setter(_set_full_name)

class Person(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "person"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]

    # Writable hybrid - not using readonly_field
    full_name: Annotated[str, _full_name_hybrid]
```

!!! warning "Important"
    Hybrid property functions must be defined **outside** the class body. The `@hybrid_property` decorator cannot be used directly on class methods because SQLCrucible generates a separate SQLAlchemy model class.

## association_proxy

An `association_proxy` provides a shortcut to attributes on related objects.

### Basic Usage

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlcrucible import SAType
from sqlcrucible import SQLAlchemyField

class Department(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "department"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]

class Employee(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "employee"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]
    department_id: Annotated[UUID, mapped_column(ForeignKey("department.id"))]

    # Relationship to Department
    department = readonly_field(
        Department,
        SQLAlchemyField(
            name="department",
            attr=relationship(lambda: SAType[Department]),
        ),
    )

    # Proxy to department.name
    department_name: Annotated[
        str, association_proxy("department", "name")
    ] = readonly_field(str)
```

### Using in Queries

```python
with Session(engine) as session:
    # Filter by association proxy
    engineers = session.scalars(
        select(SAType[Employee]).where(
            SAType[Employee].department_name == "Engineering"
        )
    ).all()
```

### Writable association_proxy

Use a `creator` function to make the proxy writable:

```python
class Employee(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "employee"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    department_id: Annotated[UUID, mapped_column(ForeignKey("department.id"))]

    department = readonly_field(
        Department,
        SQLAlchemyField(
            name="department",
            attr=relationship(lambda: SAType[Department]),
        ),
    )

    # Writable proxy - creates new Department when assigned
    department_name: Annotated[
        str,
        association_proxy(
            "department",
            "name",
            creator=lambda name: SAType[Department](id=uuid4(), name=name),
        ),
    ]
```

## Important Notes

### Accessing Values

When using `readonly_field`, computed values are available on Pydantic instances loaded via `from_sa_model()`:

```python
sa_person = session.scalar(select(SAType[Person]))
person = Person.from_sa_model(sa_person)

# Value is available on the Pydantic instance
print(person.full_name)  # "John Doe"
```

For use in SQL queries (WHERE, ORDER BY), use `SAType[Entity]`:

```python
# Use SAType for query expressions
select(SAType[Person]).where(SAType[Person].full_name == "John Doe")
```

### Lambda Syntax

You can use inline lambdas for simple hybrid properties:

```python
class Person(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "person"}

    first_name: Annotated[str, mapped_column()]
    last_name: Annotated[str, mapped_column()]

    full_name: Annotated[
        str, hybrid_property(lambda self: f"{self.first_name} {self.last_name}")
    ] = readonly_field(str)
```
