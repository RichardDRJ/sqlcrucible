# Relationships

## Defining Relationships

Use `readonly_field` to define relationship fields that are loaded from the SQLAlchemy model but not part of the entity's constructor:

```python
from typing import Annotated
from uuid import UUID, uuid4
from pydantic import Field
from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, relationship
from sqlcrucible import SQLCrucibleBaseModel, SAType
from sqlcrucible.entity.fields import readonly_field

class Artist(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

class Track(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "track"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    artist_id: Annotated[UUID, mapped_column(ForeignKey("artist.id"))]

    # Read-only relationship field - pass descriptor directly
    artist = readonly_field(
        Artist,
        relationship(lambda: SAType[Artist], back_populates="tracks"),
    )
```

!!! tip
    Use a lambda for the relationship target to avoid circular import issues.

## How `readonly_field` Works

The `readonly_field` descriptor:

1. **Excludes the field from Pydantic validation** — it won't appear in the model's `__init__`
2. **Defines a SQLAlchemy relationship** on the generated model
3. **Loads the related entity** when accessed via `from_sa_model()`

When you query a `Track` and call `from_sa_model()`, the `artist` relationship is automatically converted to an `Artist` entity.

## Advanced Usage

You can pass both a descriptor (like `relationship`, `hybrid_property`, or `association_proxy`) and `SQLAlchemyField` in any order. This gives you full control over both the descriptor and its SQLAlchemy configuration:

```python
# Pass descriptor first, then SQLAlchemyField for custom name
artist = readonly_field(
    Artist,
    relationship(lambda: SAType[Artist]),
    SQLAlchemyField(name="custom_artist_col"),
)

# Or pass SQLAlchemyField first - order doesn't matter
artist = readonly_field(
    Artist,
    SQLAlchemyField(name="custom_artist_col"),
    relationship(lambda: SAType[Artist]),
)
```

## Important Notes

- **Cyclical references are not supported.** If `Artist` has a `tracks` relationship and `Track` has an `artist` relationship, use `readonly_field` on at least one side to break the cycle.

- **Pydantic compatibility**: Either inherit from `SQLCrucibleBaseModel` (which includes the necessary config), or add `model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))` to your model (import from `sqlcrucible.entity.fields`).

- **Accessing without a backing model**: Accessing a `readonly_field` on an entity not loaded via `from_sa_model()` raises `RuntimeError`.

## Example: One-to-Many Relationship

```python
class Artist(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "artist"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

    # One-to-many: artist has many tracks
    tracks = readonly_field(
        list["Track"],
        relationship(lambda: SAType[Track], back_populates="artist"),
    )

class Track(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "track"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    artist_id: Annotated[UUID, mapped_column(ForeignKey("artist.id"))]

    # Many-to-one: track belongs to artist
    artist = readonly_field(
        Artist,
        relationship(lambda: SAType[Artist], back_populates="tracks"),
    )
```
