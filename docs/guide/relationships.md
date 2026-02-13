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
from sqlcrucible import readonly_field

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

- **Pydantic compatibility**: Either inherit from `SQLCrucibleBaseModel` (which includes the necessary config), or add `model_config = ConfigDict(ignored_types=(ReadonlyFieldDescriptor,))` to your model (import from `sqlcrucible`).

- **Accessing without a backing model**: Accessing a `readonly_field` on an entity not loaded via `from_sa_model()` raises `RuntimeError`.

## Serialisation

By default, `readonly_field` values are **excluded** from `model_dump()` and `model_dump_json()`. This is by design — they are not Pydantic model fields.

To include a readonly relationship in serialised output, wrap it with `computed_field`:

```python
from pydantic import computed_field

class Track(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "track"}
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str
    artist_id: Annotated[UUID, mapped_column(ForeignKey("artist.id"))]

    artist = computed_field(readonly_field(
        Artist,
        relationship(lambda: SAType[Artist]),
    ))
```

`ReadonlyFieldDescriptor` is a `property` subclass, so Pydantic's `computed_field` can infer the return type directly — no intermediate `@property` wrapper needed.

!!! warning
    If **both** sides of a bidirectional relationship wrap `readonly_field` with `computed_field`, Pydantic will detect a circular reference during `model_dump()` and raise a `ValueError`. Only expose one side of a cycle via `computed_field`.

## Caching and Identity

### Per-instance caching

`readonly_field` caches the converted value per instance, so repeated access returns the same object:

```python
track = Track.from_sa_model(track_sa)
track.artist is track.artist  # True — same object
```

This applies to all field types — entities, lists, and scalars.

### Identity preservation

Within a single `from_sa_model()` call, an identity map ensures that the same SQLAlchemy model instance always converts to the same entity. This means bidirectional relationships preserve object identity:

```python
author = Author.from_sa_model(author_sa)
author.tracks[0].artist is author  # True — same entity, not a copy
```

Each top-level `from_sa_model()` call creates a fresh identity map, so separate calls produce independent instances:

```python
first = Author.from_sa_model(author_sa)
second = Author.from_sa_model(author_sa)
first is not second  # True — different calls, different instances
```

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
