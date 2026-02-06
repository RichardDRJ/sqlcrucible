# Advanced Usage

## Customizing the Generated Model

For most use cases, SQLCrucible's built-in support for ORM descriptors is sufficient. See the [ORM Descriptors](orm-descriptors.md) guide for `hybrid_property` and `association_proxy` support.

For advanced customization beyond what's covered there, you can override `__sqlalchemy_type__` with a `lazyproperty`:

```python
from sqlcrucible.entity.core import lazyproperty
from sqlcrucible import SQLCrucibleEntity

def user_sqlalchemy_type(cls: type["User"]):
    class CustomModel(cls.__sqlalchemy_automodel__):
        def custom_method(self):
            return f"Custom: {self.name}"

    return CustomModel

class User(SQLCrucibleEntity):
    __sqlalchemy_params__ = {"__tablename__": "user"}
    name: str

    __sqlalchemy_type__ = lazyproperty(user_sqlalchemy_type)
```

This allows you to add custom methods or any other SQLAlchemy-specific functionality to the generated model.

## Reusing Existing SQLAlchemy Models

You can attach a SQLCrucible entity to an existing SQLAlchemy model:

```python
from typing import Annotated
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlcrucible import SQLCrucibleEntity

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
```

### Creating "Views" with Subset of Fields

You can create multiple entity classes that map to the same SQLAlchemy model but expose different fields:

```python
from typing import Annotated
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleEntity

# Full entity with all fields
class User(SQLCrucibleEntity):
    __sqlalchemy_type__ = UserModel

    id: Annotated[int, mapped_column(primary_key=True)]
    name: str
    email: str

# Summary view with only some fields
class UserSummary(SQLCrucibleEntity):
    __sqlalchemy_type__ = UserModel

    id: Annotated[int, mapped_column(primary_key=True)]
    name: str
```

## Type Stub Generation

SQLCrucible dynamically generates SQLAlchemy model classes at runtime. While this provides flexibility, Python's type system cannot represent these dynamically-created types — type checkers only see `type[Any]` for `__sqlalchemy_type__`, losing all column information.

Type stubs (`.pyi` files) solve this by providing static type declarations. With generated stubs:

- `Artist.__sqlalchemy_type__.name` is recognized as `InstrumentedAttribute[str]`
- Invalid column access produces a type error
- IDE autocompletion works for column names

### Generating Stubs

```bash
# Generate stubs for a module
python -m sqlcrucible.stubs myapp.models

# Multiple modules
python -m sqlcrucible.stubs myapp.models myapp.other_models

# Custom output directory (default: stubs/)
python -m sqlcrucible.stubs myapp.models --output typings/
```

!!! tip
    For projects with entities spread across many modules, create a single module that imports them all, then generate stubs from that.

### Configuring Type Checkers

=== "Pyright"

    ```toml
    # pyproject.toml
    [tool.pyright]
    stubPath = "stubs"
    ```

=== "Mypy"

    ```toml
    # pyproject.toml
    [tool.mypy]
    mypy_path = "stubs"
    ```

=== "ty"

    ```toml
    # pyproject.toml
    [tool.ty.environment]
    extra-paths = ["stubs"]
    ```

### Keeping Stubs Updated

Regenerate stubs whenever you add or modify entity fields. Consider adding stub generation to your CI process or using a pre-commit hook.
