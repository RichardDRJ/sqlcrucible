# SQLCrucible

Get the full power of Pydantic for your API and the full power of SQLAlchemy for your database, without compromising on either.

SQLCrucible is a compatibility layer that lets you define a single model class that works as both a Pydantic model and a SQLAlchemy table, with explicit conversion between the two.

## Why SQLCrucible?

In a FastAPI/SQLAlchemy web application, you typically need two sets of models:

- **Pydantic models** for API serialization, validation, and documentation
- **SQLAlchemy models** for database persistence and queries

These models often mirror each other field-for-field, leading to:

- **Duplication** — the same fields defined twice, in two places
- **Drift** — models get out of sync as the codebase evolves
- **Boilerplate** — manual conversion code for every database operation

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

## When to Use SQLCrucible

SQLCrucible is a good fit when:

- You're building an API (FastAPI, Litestar, etc.) backed by a SQL database
- Your API models and database models are structurally similar
- You want SQLAlchemy's full feature set (inheritance, relationships, hybrid properties) without abstraction layers

SQLCrucible may not be the best fit when:

- Your API models and database models are fundamentally different shapes
- You need to support multiple database backends with different schemas
- You prefer a more opinionated/implicit approach
