# SQLCrucible

Get the full power of Pydantic for your API and the full power of SQLAlchemy for your database, without compromising on either.

SQLCrucible lets you define a single model class that works as both a Pydantic model and a SQLAlchemy table, with explicit conversion between the two. Your Pydantic models stay pure Pydantic (working with FastAPI, validation, serialization), your SQLAlchemy models stay pure SQLAlchemy (supporting relationships, inheritance, Alembic), and conversion only happens when you ask for it.

## Key Features

- **Explicit conversion** — `to_sa_model()` and `from_sa_model()` make it clear when you're crossing the boundary between Pydantic and SQLAlchemy
- **Native SQLAlchemy** — use `mapped_column()`, `relationship()`, and `__mapper_args__` directly; if SQLAlchemy supports it, so does SQLCrucible
- **Escape hatches everywhere** — mix with plain SQLAlchemy models, attach entities to existing tables, customize generated models, or drop down to raw queries
- **Full inheritance support** — single table, joined table, and concrete table inheritance all work out of the box
- **Type stub generation** — generate `.pyi` stubs for IDE autocompletion and type checking of SQLAlchemy columns
- **Multiple frameworks** — works with Pydantic, dataclasses, and attrs

## Example

```python
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, mapped_column

from sqlcrucible import SAType, SQLCrucibleBaseModel

class Artist(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {"__tablename__": "artist"}

    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    name: str

engine = create_engine("sqlite:///:memory:")
SAType[Artist].__table__.metadata.create_all(engine)

artist = Artist(name="Bob Dylan")
with Session(engine) as session:
    session.add(artist.to_sa_model())
    session.commit()

with Session(engine) as session:
    sa_artist = session.scalar(
        select(SAType[Artist]).where(SAType[Artist].name == "Bob Dylan")
    )
    artist = Artist.from_sa_model(sa_artist)
```

## Installation

```bash
pip install sqlcrucible
```

## Documentation

Full documentation is available at [sqlcrucible.rdrj.uk](https://sqlcrucible.rdrj.uk/).

---

<p align="center">
  🏴󠁧󠁢󠁳󠁣󠁴󠁿 Made with haggis
</p>
