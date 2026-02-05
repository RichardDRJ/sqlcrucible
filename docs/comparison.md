# Comparison with SQLModel

[SQLModel](https://sqlmodel.tiangolo.com/) is a popular library that also bridges Pydantic and SQLAlchemy. This page compares the two approaches to help you choose the right tool for your project.

## Philosophy

### SQLCrucible's Approach

- **Explicit conversion** between Pydantic and SQLAlchemy models via `to_sa_model()` and `from_sa_model()`
- **Native SQLAlchemy constructs** — uses `mapped_column()`, `relationship()`, `__mapper_args__` directly
- **Pure Pydantic models** that work with any Pydantic tooling
- **Full SQLAlchemy feature support** without waiting for library updates

### SQLModel's Approach

- **Single class** serves both purposes (less boilerplate for simple cases)
- **Custom field types** and abstractions over SQLAlchemy
- **Tighter integration** means less explicit conversion code
- **More opinionated** design choices

## Feature Comparison

| Feature | SQLCrucible | SQLModel |
|---------|-------------|----------|
| Single class definition | Yes | Yes |
| Pure Pydantic models | Yes | No (hybrid) |
| Pure SQLAlchemy models | Yes | No (hybrid) |
| Native `mapped_column()` | Yes | No |
| Native `relationship()` | Yes | Limited |
| All inheritance patterns | Yes | Limited |
| Custom type converters | Yes | Limited |
| Alembic compatibility | Full | Full |
| FastAPI integration | Full | Built-in |

## Code Comparison

### Basic Model

=== "SQLCrucible"

    ```python
    from typing import Annotated
    from uuid import UUID, uuid4
    from pydantic import Field
    from sqlalchemy.orm import mapped_column
    from sqlcrucible import SQLCrucibleBaseModel

    class User(SQLCrucibleBaseModel):
        __sqlalchemy_params__ = {"__tablename__": "user"}

        id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
        name: str
        email: str
    ```

=== "SQLModel"

    ```python
    from uuid import UUID, uuid4
    from sqlmodel import SQLModel, Field

    class User(SQLModel, table=True):
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        name: str
        email: str
    ```

### Database Operations

=== "SQLCrucible"

    ```python
    # Create
    user = User(name="Alice", email="alice@example.com")
    session.add(user.to_sa_model())
    session.commit()

    # Query
    sa_user = session.scalar(select(SAType[User]).where(SAType[User].name == "Alice"))
    user = User.from_sa_model(sa_user)
    ```

=== "SQLModel"

    ```python
    # Create
    user = User(name="Alice", email="alice@example.com")
    session.add(user)
    session.commit()

    # Query
    user = session.exec(select(User).where(User.name == "Alice")).first()
    ```

### Relationships

=== "SQLCrucible"

    ```python
    from sqlalchemy.orm import relationship
    from sqlcrucible.entity.fields import readonly_field
    from sqlcrucible.entity.annotations import SQLAlchemyField

    class Author(SQLCrucibleBaseModel):
        __sqlalchemy_params__ = {"__tablename__": "author"}
        id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
        name: str

        books = readonly_field(
            list["Book"],
            SQLAlchemyField(
                name="books",
                attr=relationship(lambda: Book.__sqlalchemy_type__),
            ),
        )
    ```

=== "SQLModel"

    ```python
    from sqlmodel import Relationship

    class Author(SQLModel, table=True):
        id: UUID = Field(default_factory=uuid4, primary_key=True)
        name: str

        books: list["Book"] = Relationship(back_populates="author")
    ```

## When to Choose SQLCrucible

Choose SQLCrucible if you:

- Want full SQLAlchemy feature support (all inheritance patterns, hybrid properties, etc.)
- Need pure Pydantic models that work with all Pydantic tooling
- Prefer explicit over implicit conversion
- Have complex models that benefit from SQLAlchemy's full power
- Want to use native SQLAlchemy constructs without abstractions

## When to Choose SQLModel

Choose SQLModel if you:

- Have simple models without complex inheritance or relationships
- Prefer less boilerplate over explicit control
- Want tighter FastAPI integration out of the box
- Are comfortable with the hybrid model approach
- Don't need advanced SQLAlchemy features
