# SQLCrucible

Get the full power of Pydantic for your API and the full power of SQLAlchemy for your database, without compromising on either.

SQLCrucible is a compatibility layer that lets you define a single model class that works as both a Pydantic model and a SQLAlchemy table, with explicit conversion between the two.

## Why SQLCrucible?

### The Problem

In a FastAPI/SQLAlchemy web application, you typically need two sets of models:

- **Pydantic models** for API serialization, validation, and documentation
- **SQLAlchemy models** for database persistence and queries

These models often mirror each other field-for-field, leading to:

- **Duplication** — the same fields defined twice, in two places
- **Drift** — models get out of sync as the codebase evolves
- **Boilerplate** — manual conversion code for every database operation

### The Solution

With SQLCrucible, you define your model once:

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

You get:
- A **Pydantic model** that works with FastAPI, serialization, and validation
- A **SQLAlchemy table** with proper column types and constraints
- **Type-safe conversion** methods between the two

### When to Use SQLCrucible

SQLCrucible is a good fit when:

- You're building an API (FastAPI, Litestar, etc.) backed by a SQL database
- Your API models and database models are structurally similar
- You want SQLAlchemy's full feature set (inheritance, relationships, hybrid properties) without abstraction layers

SQLCrucible may not be the best fit when:

- Your API models and database models are fundamentally different shapes
- You need to support multiple database backends with different schemas
- You prefer a more opinionated/implicit approach

## Installation

```bash
pip install sqlcrucible
```

Or with uv:

```bash
uv add sqlcrucible
```

## Quick Start

Here's a complete example showing the typical workflow:

```python
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, mapped_column

from sqlcrucible import SAType, SQLCrucibleBaseModel

# 1. Define your entity
class Artist(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "artist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

# 2. Create the database tables
engine = create_engine("sqlite:///:memory:")
SAType[Artist].__table__.metadata.create_all(engine)

# 3. Create an entity and save it
artist = Artist(name="Bob Dylan")
with Session(engine) as session:
    session.add(artist.to_sa_model())  # Convert to SQLAlchemy model
    session.commit()

# 4. Query and convert back
with Session(engine) as session:
    sa_artist = session.scalar(
        select(SAType[Artist]).where(SAType[Artist].name == "Bob Dylan")
    )
    artist = Artist.from_sa_model(sa_artist)  # Convert back to entity
    print(artist.name)  # "Bob Dylan"
```

The `Artist` class is a standard Pydantic model — it works with FastAPI, has validation, and serializes to JSON. When you need to interact with the database, you explicitly convert to and from the SQLAlchemy model.

<details><summary>Expand to see the equivalent hand-written code for the Artist class</summary>

```python
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from sqlalchemy.orm import mapped_column, DeclarativeBase, Mapped
from typing import Any, Self

class Base(DeclarativeBase): ...

class ArtistSQLAlchemyModel(Base):
    __tablename__ = "artist"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]

class Artist(BaseModel):
    __sqlalchemy_type__: type[Any] = ArtistSQLAlchemyModel

    id: UUID = Field(default_factory=uuid4)
    name: str

    def to_sa_model(self) -> ArtistSQLAlchemyModel:
        return ArtistSQLAlchemyModel(
            id=self.id,
            name=self.name
        )

    @classmethod
    def from_sa_model(cls, sa_model: ArtistSQLAlchemyModel) -> Self:
        return cls(
            id=sa_model.id,
            name=sa_model.name
        )
```
</details>

## Design Principles

### Explicit is better than implicit

Conversion between Pydantic and SQLAlchemy models only happens when you ask for it — by calling `to_sa_model()` or `from_sa_model()`. By keeping conversion explicit, SQLCrucible ensures your Pydantic models remain "pure" Pydantic (working seamlessly with FastAPI, standard serialization, and any other Pydantic-compatible tooling) and your SQLAlchemy models remain "pure" SQLAlchemy (supporting anything SQLAlchemy supports, and working seamlessly with SQLAlchemy tooling like Alembic).

### Don't reinvent SQLAlchemy

SQLCrucible uses native SQLAlchemy constructs directly. You define columns with `mapped_column()`, relationships with `relationship()`, and inheritance with `__mapper_args__` — exactly as you would in plain SQLAlchemy. If SQLAlchemy supports it, you can use it immediately.

### Everything has an escape hatch

SQLCrucible is designed to get out of your way:

- Mix SQLCrucible entities with standard SQLAlchemy models in the same database
- Use only the parts you need — you can even attach entities to existing SQLAlchemy models
- Customize the generated SQLAlchemy model with hybrid properties, custom methods, etc.
- Drop down to raw SQLAlchemy queries whenever needed

---

## Usage Guide

### Sharing Metadata Across Entities

When defining multiple entities, you can use a custom base class to change the `MetaData` instance they use:

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

### Configuring the SQLAlchemy Model with `__sqlalchemy_params__`

The `__sqlalchemy_params__` dictionary is placed directly into the generated SQLAlchemy model's class namespace. This means you can use it for any class-level attribute SQLAlchemy expects:

| Key | Purpose |
|-----|---------|
| `__tablename__` | The database table name |
| `__table_args__` | Table-level constraints, indexes, etc. |
| `__mapper_args__` | Mapper configuration (polymorphism, eager loading, etc.) |
| `__abstract__` | Mark as abstract base (no table created) |
| `metadata` | Custom `MetaData` instance |

You can also use it to add columns or attributes that exist only on the SQLAlchemy model, not on the entity:

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

### Relationships

Use `readonly_field` to define relationship fields that are loaded from the SQLAlchemy model but not part of the entity's constructor:

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlcrucible.entity.fields import readonly_field
from sqlcrucible.entity.annotations import SQLAlchemyField

class Artist(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

class Track(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "track"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    artist_id: Annotated[UUID, mapped_column(ForeignKey("artist.id"))]

    # Read-only relationship field
    artist = readonly_field(
        Artist,
        SQLAlchemyField(
            name="artist",
            attr=relationship(lambda: Artist.__sqlalchemy_type__),
        ),
    )
```

> :bulb: **Tip:** Use a lambda for the relationship target to avoid circular import issues.

### Custom Type Converters

Use `ConvertToSAWith` and `ConvertFromSAWith` to customize conversion between your entity and the SQLAlchemy model:

```python
from datetime import timedelta
from sqlcrucible.entity.annotations import ConvertFromSAWith, ConvertToSAWith, SQLAlchemyField

class Track(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "track"}

    # Store as integer seconds in database, use timedelta in Python
    length: Annotated[
        timedelta,
        mapped_column(),
        SQLAlchemyField(name="length_seconds", tp=int),
        ConvertToSAWith(lambda td: td.total_seconds()),
        ConvertFromSAWith(lambda s: timedelta(seconds=s)),
    ]
```

### Customizing Field Mapping

By default, all entity fields with a `mapped_column()` annotation are included in the generated SQLAlchemy model.

#### Excluding Fields with `ExcludeSAField`

Use `ExcludeSAField` to exclude a field from the SQLAlchemy model while keeping it on the Pydantic entity:

```python
from sqlcrucible.entity.annotations import ExcludeSAField

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

> **Note:** Fields marked with `ExcludeSAField()` must have a default value if you plan to use `from_sa_model()`, since there's no database column to populate them from.

#### Customizing Fields with `SQLAlchemyField`

`SQLAlchemyField` allows you to customize how entity fields map to SQLAlchemy columns:

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `name` | Rename the mapped column | `SQLAlchemyField(name="db_column")` |
| `tp` | Override the mapped type | `SQLAlchemyField(tp=int)` |
| `attr` | Provide a Mapped[] attribute directly | `SQLAlchemyField(attr=relationship(...))` |

**Renaming a column:**

```python
class User(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "user"}

    # Entity field 'email' maps to column 'email_address' in the database
    email: Annotated[str, SQLAlchemyField(name="email_address")]
```

### Inheritance

SQLCrucible supports all three SQLAlchemy inheritance patterns. Each uses `__sqlalchemy_params__` with `__mapper_args__` to configure polymorphism.

#### Single Table Inheritance

All subclasses share one table with a discriminator column:

```python
from sqlalchemy import String
from sqlcrucible.entity.annotations import ExcludeSAField

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__tablename__": "animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))]
    name: str

class Dog(Animal):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "dog"}}
    bones_chewed: Annotated[int | None, mapped_column(nullable=True)] = None
    # Override default but exclude from SA model (column exists on parent)
    type: Annotated[str, ExcludeSAField()] = Field(default="dog")

class Cat(Animal):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "cat"}}
    hours_napped: Annotated[int | None, mapped_column(nullable=True)] = None
    type: Annotated[str, ExcludeSAField()] = Field(default="cat")
```

#### Joined Table Inheritance

Each subclass has its own table with a foreign key to the parent:

```python
from sqlalchemy import ForeignKey

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__tablename__": "animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))]
    name: str

class Dog(Animal):
    __sqlalchemy_params__ = {
        "__tablename__": "dog",
        "__mapper_args__": {"polymorphic_identity": "dog"},
    }
    id: Annotated[UUID, mapped_column(ForeignKey("animal.id"), primary_key=True)] = Field(default_factory=uuid4)
    bones_chewed: int | None = None
    type: Annotated[str, ExcludeSAField()] = Field(default="dog")
```

#### Concrete Table Inheritance

Each subclass is a completely independent table:

```python
class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__abstract__": True,
        "__mapper_args__": {"polymorphic_on": "type"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))]
    name: str

class Dog(Animal):
    __sqlalchemy_params__ = {
        "__tablename__": "dog",
        "__mapper_args__": {"polymorphic_identity": "dog", "concrete": True},
    }
    # Must redefine ALL columns for concrete table inheritance
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))] = Field(default="dog")
    name: str
    bones_chewed: int | None = None
```

#### Polymorphic Round-Trip

When using inheritance, `from_sa_model()` automatically returns the correct subclass:

```python
dog_sa = Dog.__sqlalchemy_type__(id=uuid4(), name="Fido", type="dog", bones_chewed=42)

# Load via the base class — returns Dog, not Animal
animal = Animal.from_sa_model(dog_sa)
assert isinstance(animal, Dog)
assert animal.bones_chewed == 42
```

### Customizing the Generated Model

Override `__sqlalchemy_type__` with a `lazyproperty` to customize the generated SQLAlchemy model:

```python
from sqlalchemy.ext.hybrid import hybrid_property
from sqlcrucible.utils.properties import lazyproperty
from sqlcrucible import SQLCrucibleEntity

def user_sqlalchemy_type(cls: type["User"]):
    class CustomModel(cls.__sqlalchemy_automodel__):
        @hybrid_property
        def full_name(self):
            return f"{self.first_name} {self.last_name}"

    return CustomModel

class User(SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__tablename__": "user"}
    first_name: str
    last_name: str

    __sqlalchemy_type__ = lazyproperty(user_sqlalchemy_type)
```

### Reusing Existing SQLAlchemy Models

You can attach a SQLCrucible entity to an existing SQLAlchemy model:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

# Your existing SQLAlchemy model
class UserModel(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    email: Mapped[str] = mapped_column()

# Attach an entity to it
class User(SQLCrucibleEntity):
    __sqlalchemy_type__ = UserModel

    id: Annotated[int, mapped_column(primary_key=True)]
    name: str
    email: str

# Or create a "view" with only some fields
class UserSummary(SQLCrucibleEntity):
    __sqlalchemy_type__ = UserModel

    id: Annotated[int, mapped_column(primary_key=True)]
    name: str
```

### Type Stub Generation

SQLCrucible dynamically generates SQLAlchemy model classes at runtime. While this provides flexibility, Python's type system cannot represent these dynamically-created types — type checkers only see `type[Any]` for `__sqlalchemy_type__`, losing all column information.

Type stubs (`.pyi` files) solve this by providing static type declarations. With generated stubs:

- `Artist.__sqlalchemy_type__.name` is recognized as `InstrumentedAttribute[str]`
- Invalid column access produces a type error
- IDE autocompletion works for column names

#### Generating Stubs

```bash
# Generate stubs for a module
python -m sqlcrucible.stubs myapp.models

# Multiple modules
python -m sqlcrucible.stubs myapp.models myapp.other_models

# Custom output directory (default: stubs/)
python -m sqlcrucible.stubs myapp.models --output typings/
```

**Tip:** For projects with entities spread across many modules, create a single module that imports them all, then generate stubs from that.

#### Configuring Type Checkers

**Pyright:**

```toml
# pyproject.toml
[tool.pyright]
stubPath = "stubs"
```

**Mypy:**

```toml
# pyproject.toml
[tool.mypy]
mypy_path = "stubs"
```

**ty:**

```toml
# pyproject.toml
[tool.ty.environment]
extra-paths = ["stubs"]
```

#### Keeping Stubs Updated

Regenerate stubs whenever you add or modify entity fields. Consider adding stub generation to your CI process or using a pre-commit hook.

---

## Framework Support

SQLCrucible works with multiple Python model frameworks:

- **Pydantic**: Inherit from `SQLCrucibleBaseModel`
- **dataclasses**: Use `@dataclass` with `SQLCrucibleEntity`
- **attrs**: Use `@define` with `SQLCrucibleEntity`

```python
from dataclasses import dataclass, field

@dataclass
class Artist(SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__tablename__": "artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = field(default_factory=uuid4)
    name: str
```

---

## Caveats

1. **Cyclical references between model instances are not supported.** Use `readonly_field` on one side to break the cycle.

2. **Pydantic and `readonly_field`**: Either inherit from `SQLCrucibleBaseModel` (which includes the necessary config), or add `model_config = ConfigDict(ignored_types=(readonly_field,))` to your model.

3. **Forward references in relationships**: Use lambdas to avoid circular import issues: `relationship(lambda: OtherEntity.__sqlalchemy_type__)`.

4. **Concrete table inheritance** requires redefining ALL columns in each subclass.

5. **`readonly_field` requires a backing SQLAlchemy model**: Accessing a `readonly_field` on an entity not loaded via `from_sa_model()` raises `RuntimeError`.

---

## Comparison with SQLModel

[SQLModel](https://sqlmodel.tiangolo.com/) takes a different approach: it creates a single class that *is* both a Pydantic model and a SQLAlchemy model simultaneously.

**SQLCrucible's approach:**
- Keeps Pydantic and SQLAlchemy separate with explicit conversion
- Uses native SQLAlchemy constructs (`mapped_column`, `relationship`, `__mapper_args__`)
- Your Pydantic models remain "pure" and work with any Pydantic tooling
- Full SQLAlchemy feature support without waiting for library updates

**SQLModel's approach:**
- Single class serves both purposes (less boilerplate for simple cases)
- Custom field types and abstractions over SQLAlchemy
- Tighter integration means less explicit conversion code

Choose SQLCrucible if you want full SQLAlchemy compatibility and pure Pydantic models. Choose SQLModel if you prefer a more integrated, opinionated approach for simpler use cases.

---

Made with haggis 🏴󠁧󠁢󠁳󠁣󠁴󠁿
