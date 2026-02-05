# Defining Entities

## Basic Entity Definition

An entity is a class that serves as both a Pydantic model and a SQLAlchemy table definition. Use `mapped_column()` in `Annotated` to mark fields that should become database columns:

```python
from typing import Annotated
from uuid import UUID, uuid4
from pydantic import Field
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel

class Artist(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "artist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: Annotated[str, mapped_column()]
```

Fields without `mapped_column()` are Pydantic-only and won't appear in the database.

## Sharing Metadata Across Entities

When defining multiple entities, use a custom base class to share a `MetaData` instance:

```python
from sqlalchemy import MetaData

class BaseEntity(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__abstract__": True, "metadata": MetaData()}

class Artist(BaseEntity):
    __sqlalchemy_params__ = {"__tablename__": "artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

class Album(BaseEntity):
    __sqlalchemy_params__ = {"__tablename__": "album"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    title: str
```

## Configuring with `__sqlalchemy_params__`

The `__sqlalchemy_params__` dictionary is placed directly into the generated SQLAlchemy model's class namespace. This means you can use it for any class-level attribute SQLAlchemy expects:

| Key | Purpose |
|-----|---------|
| `__tablename__` | The database table name |
| `__table_args__` | Table-level constraints, indexes, etc. |
| `__mapper_args__` | Mapper configuration (polymorphism, eager loading, etc.) |
| `__abstract__` | Mark as abstract base (no table created) |
| `metadata` | Custom `MetaData` instance |

### Adding SQLAlchemy-Only Columns

You can use `__sqlalchemy_params__` to add columns that exist only on the SQLAlchemy model:

```python
from sqlalchemy import Column, String, Index
from sqlalchemy.orm import mapped_column

class User(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__tablename__": "user",
        # Add a column only to the SQLAlchemy model
        "legacy_id": Column(String(50), nullable=True),
        # Add table-level constraints
        "__table_args__": (
            Index("ix_user_email", "email"),
        ),
    }

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    email: str
```

The `legacy_id` column exists in the database and on `SAType[User]`, but isn't part of the `User` Pydantic model — useful for database-only fields, migration artifacts, or columns managed by triggers.
