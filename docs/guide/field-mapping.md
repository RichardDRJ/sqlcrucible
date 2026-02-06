# Field Mapping

## Default Behavior

By default, all entity fields with a `mapped_column()` annotation are included in the generated SQLAlchemy model with the same name and type.

## Excluding Fields with `ExcludeSAField`

Use `ExcludeSAField` to exclude a field from the SQLAlchemy model while keeping it on the Pydantic entity:

```python
from typing import Annotated
from pydantic import Field
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible import ExcludeSAField

class Dog(Animal):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "dog"}}

    bones_chewed: int | None = None
    # Exclude 'type' from Dog's SQLAlchemy model — it's inherited from Animal
    type: Annotated[str, ExcludeSAField()] = Field(default="dog")
```

This is useful when:

- A child class overrides a parent field's default value (as with `type` above)
- You want a field on the Pydantic model that doesn't exist in the database
- You're using single-table inheritance and the column is already defined on the parent

!!! note
    Fields marked with `ExcludeSAField()` must have a default value if you plan to use `from_sa_model()`, since there's no database column to populate them from.

## Customizing Fields with `SQLAlchemyField`

`SQLAlchemyField` allows you to customize how entity fields map to SQLAlchemy columns:

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `name` | Rename the mapped column | `SQLAlchemyField(name="db_column")` |
| `tp` | Override the mapped type | `SQLAlchemyField(tp=int)` |
| `attr` | Provide a Mapped[] attribute directly | `SQLAlchemyField(attr=relationship(...))` |

### Renaming a Column

```python
from typing import Annotated
from uuid import UUID, uuid4
from pydantic import Field
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible import SQLAlchemyField

class User(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "user"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    # Entity field 'email' maps to column 'email_address' in the database
    email: Annotated[str, SQLAlchemyField(name="email_address")]
```

### Overriding the Column Type

```python
from datetime import timedelta
from typing import Annotated
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible import SQLAlchemyField

class Task(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "task"}

    # Store timedelta as integer seconds in database
    duration: Annotated[
        timedelta,
        mapped_column(),
        SQLAlchemyField(tp=int),
    ]
```

When overriding types, you'll typically also need to provide custom converters. See [Type Conversion](type-conversion.md) for details.
