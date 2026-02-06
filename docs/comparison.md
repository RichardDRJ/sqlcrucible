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
| Native `relationship()` | Yes | Limited[^1] |
| `hybrid_property` | Yes | Workaround[^2] |
| `association_proxy` | Yes | No |
| All inheritance patterns | Yes | Limited[^3] |
| Alembic compatibility | Full | Full |
| FastAPI integration | Full | Built-in[^4] |

[^1]: SQLModel's `Relationship` wrapper has known issues with `back_populates` configuration ([#383](https://github.com/fastapi/sqlmodel/issues/383), [#932](https://github.com/fastapi/sqlmodel/discussions/932)) and inheritance ([#167](https://github.com/fastapi/sqlmodel/issues/167), [#507](https://github.com/fastapi/sqlmodel/issues/507)).

[^2]: SQLModel has [type detection issues](https://github.com/fastapi/sqlmodel/issues/299) requiring a `ClassVar` workaround. Full support via [PR #801](https://github.com/fastapi/sqlmodel/pull/801) remains unmerged.

[^3]: SQLModel [recommends against inheriting from table models](https://sqlmodel.tiangolo.com/tutorial/fastapi/multiple-models/), limiting support for joined-table and single-table inheritance patterns ([#488](https://github.com/fastapi/sqlmodel/issues/488)).

[^4]: SQLModel models with `table=True` [skip Pydantic validation by design](https://github.com/fastapi/sqlmodel/issues/52), meaning required fields aren't validated ([#406](https://github.com/fastapi/sqlmodel/issues/406), [#1665](https://github.com/fastapi/sqlmodel/discussions/1665)). The workaround requires separate validation and table models. SQLCrucible models are pure Pydantic and always validate.

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
    from sqlcrucible import SAType
    from sqlcrucible import readonly_field
    from sqlcrucible import SQLAlchemyField

    class Author(SQLCrucibleBaseModel):
        __sqlalchemy_params__ = {"__tablename__": "author"}
        id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
        name: str

        books = readonly_field(
            list["Book"],
            SQLAlchemyField(
                name="books",
                attr=relationship(lambda: SAType[Book]),
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

### Computed Properties (hybrid_property)

=== "SQLCrucible"

    ```python
    from sqlalchemy.ext.hybrid import hybrid_property
    from sqlcrucible import readonly_field

    def _full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    class Person(SQLCrucibleBaseModel):
        __sqlalchemy_params__ = {"__tablename__": "person"}

        first_name: Annotated[str, mapped_column()]
        last_name: Annotated[str, mapped_column()]

        # Works in both Python and SQL queries
        full_name: Annotated[str, hybrid_property(_full_name)] = readonly_field(str)

    # Use in queries
    session.scalars(
        select(SAType[Person]).where(SAType[Person].full_name == "John Doe")
    )
    ```

=== "SQLModel"

    ```python
    from typing import ClassVar
    from sqlalchemy.ext.hybrid import hybrid_property

    class Person(SQLModel, table=True):
        first_name: str
        last_name: str

        # Requires ClassVar workaround to avoid type detection errors
        # See: https://github.com/fastapi/sqlmodel/issues/299
        @hybrid_property
        def full_name(self) -> str:
            return f"{self.first_name} {self.last_name}"

        # Must annotate as ClassVar to prevent Pydantic treating it as a field
        full_name: ClassVar[str]
    ```

### Association Proxy

=== "SQLCrucible"

    ```python
    from sqlalchemy.ext.associationproxy import association_proxy

    class Employee(SQLCrucibleBaseModel):
        __sqlalchemy_params__ = {"__tablename__": "employee"}

        department_id: Annotated[UUID, mapped_column(ForeignKey("department.id"))]

        department = readonly_field(
            Department,
            relationship(lambda: SAType[Department]),
        )

        # Direct access to department.name
        department_name: Annotated[
            str, association_proxy("department", "name")
        ] = readonly_field(str)

    # Use in queries
    session.scalars(
        select(SAType[Employee]).where(SAType[Employee].department_name == "Engineering")
    )
    ```

=== "SQLModel"

    ```python
    # SQLModel does not support association_proxy directly.
    # You would need to join and filter manually.
    ```

## When to Choose SQLCrucible

Choose SQLCrucible if you:

- Want full SQLAlchemy feature support (all inheritance patterns, `hybrid_property`, `association_proxy`, etc.)
- Need computed properties that work in both Python and SQL queries
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
