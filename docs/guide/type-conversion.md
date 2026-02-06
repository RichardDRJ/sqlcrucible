# Type Conversion

## Custom Type Converters

Use `ConvertToSAWith` and `ConvertFromSAWith` to customize conversion between your entity and the SQLAlchemy model:

```python
from datetime import timedelta
from typing import Annotated
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible import ConvertFromSAWith, ConvertToSAWith, SQLAlchemyField

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

## How the Conversion System Works

When converting between Pydantic and SQLAlchemy models, SQLCrucible uses a registry of type converters. Understanding how this works helps when dealing with complex nested types.

### Built-in Converters

The converter registry resolves conversions by finding a converter that matches the source and target types. Built-in converters handle:

- **Primitive types** (`str`, `int`, `bool`, etc.) — passed through unchanged
- **Sequences** (`list`, `tuple`, `set`, `frozenset`) — element-wise conversion with container duplication
- **Dicts and TypedDicts** — key-by-key value conversion
- **Unions** — finds the best matching branch based on type compatibility
- **Literals** — validates values against allowed literal values

### Collection Duplication

Collections are always duplicated during conversion rather than passed through by reference. This prevents SQLAlchemy operations from affecting Pydantic model state and vice versa:

```python
class Artist(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "artist"}
    tags: list[str]  # This list is copied, not shared

artist = Artist(tags=["rock", "blues"])
sa_artist = artist.to_sa_model()

# Modifying the SQLAlchemy model's list doesn't affect the original
sa_artist.tags.append("jazz")
assert "jazz" not in artist.tags  # True — they're separate lists
```

If you need strict passthrough (same object reference), register a custom no-op converter for your specific type using `ConvertToSAWith` and `ConvertFromSAWith` with identity functions.

## Dict and TypedDict Conversion

Dict conversion resolves value converters for each field. There are some important behaviours to be aware of:

### Unparameterized Dicts

An unparameterized `dict` has value type `Any`. When converting to a `TypedDict` with typed fields, the converter cannot prove that `Any` values are compatible with specific field types like nested `TypedDict`s:

```python
from typing import TypedDict, Any

class PersonDict(TypedDict):
    name: str
    age: int

class NestedDict(TypedDict):
    person: PersonDict  # Nested TypedDict
    active: bool

# This works — dict[str, Any] values convert to str/int via no-op
converter = registry.resolve(dict[str, Any], PersonDict)  # OK

# This returns None — can't prove Any -> PersonDict is valid
converter = registry.resolve(dict, NestedDict)  # None
```

!!! tip "Recommendation"
    Use parameterized dict types (`dict[str, Any]`, `dict[str, int]`) when you need predictable conversion behaviour with nested structures.

### Required Field Validation

If a target `TypedDict` has required fields that aren't present in the source dict, conversion raises `TypeError`.
