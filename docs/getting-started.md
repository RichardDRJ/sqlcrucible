# Getting Started

## Installation

Install SQLCrucible with pip:

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

## What This Replaces

Without SQLCrucible, you'd need to write equivalent code like this:

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

## Caveats

1. **Cyclical references between model instances are not supported.** Use `readonly_field` on one side to break the cycle.

2. **Pydantic and `readonly_field`**: Either inherit from `SQLCrucibleBaseModel` (which includes the necessary config), or add `model_config = ConfigDict(ignored_types=(readonly_field,))` to your model.

3. **Forward references in relationships**: Use lambdas to avoid circular import issues: `relationship(lambda: SAType[OtherEntity])`.

4. **Concrete table inheritance** requires redefining ALL columns in each subclass.

5. **`readonly_field` requires a backing SQLAlchemy model**: Accessing a `readonly_field` on an entity not loaded via `from_sa_model()` raises `RuntimeError`.
