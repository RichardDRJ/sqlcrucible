# Inheritance

SQLCrucible supports all three SQLAlchemy inheritance patterns. Each uses `__sqlalchemy_params__` with `__mapper_args__` to configure polymorphism.

## Single Table Inheritance

All subclasses share one table with a discriminator column:

```python
from typing import Annotated
from uuid import UUID, uuid7
from pydantic import Field
from sqlalchemy import String
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible import ExcludeSAField

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__tablename__": "animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid7)
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

## Joined Table Inheritance

Each subclass has its own table with a foreign key to the parent:

```python
from typing import Annotated
from uuid import UUID, uuid7
from pydantic import Field
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible import ExcludeSAField

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__tablename__": "animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid7)
    type: Annotated[str, mapped_column(String(50))]
    name: str

class Dog(Animal):
    __sqlalchemy_params__ = {
        "__tablename__": "dog",
        "__mapper_args__": {"polymorphic_identity": "dog"},
    }
    id: Annotated[UUID, mapped_column(ForeignKey("animal.id"), primary_key=True)] = Field(default_factory=uuid7)
    bones_chewed: int | None = None
    type: Annotated[str, ExcludeSAField()] = Field(default="dog")
```

## Concrete Table Inheritance

Each subclass is a completely independent table:

```python
from typing import Annotated
from uuid import UUID, uuid7
from pydantic import Field
from sqlalchemy import String
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__abstract__": True,
        "__mapper_args__": {"polymorphic_on": "type"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid7)
    type: Annotated[str, mapped_column(String(50))]
    name: str

class Dog(Animal):
    __sqlalchemy_params__ = {
        "__tablename__": "dog",
        "__mapper_args__": {"polymorphic_identity": "dog", "concrete": True},
    }
    # Must redefine ALL columns for concrete table inheritance
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid7)
    type: Annotated[str, mapped_column(String(50))] = Field(default="dog")
    name: str
    bones_chewed: int | None = None
```

!!! warning
    Concrete table inheritance requires redefining ALL columns in each subclass.

## Narrowing the discriminator

The examples above type the discriminator as `str`, which is the simplest thing that works. The cost shows up when you generate a client from these models: every subclass declares the same discriminator type, so the generated union carries no information about which variant you have.

```ts
// Every variant says `type: string`, so this does not narrow
if (animal.type === "dog") {
  animal.bones_chewed;  // not accessible without a cast
}
```

Pin each subclass to its own value instead, using `Literal`:

```python
from typing import Annotated, Literal

class Dog(Animal):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "dog"}}
    bones_chewed: Annotated[int | None, mapped_column(nullable=True)] = None
    type: Annotated[Literal["dog"], ExcludeSAField()] = "dog"  # pyright: ignore[reportIncompatibleVariableOverride]

class Cat(Animal):
    __sqlalchemy_params__ = {"__mapper_args__": {"polymorphic_identity": "cat"}}
    hours_napped: Annotated[int | None, mapped_column(nullable=True)] = None
    type: Annotated[Literal["cat"], ExcludeSAField()] = "cat"  # pyright: ignore[reportIncompatibleVariableOverride]
```

`Literal` also accepts enum members, so `Literal[AnimalType.DOG]` works if your discriminator is a `StrEnum`.

!!! warning "Keep `ExcludeSAField()`"
    The narrowed annotation still redeclares a column that already exists on the parent, so it needs `ExcludeSAField()` exactly as the `str` version did. A bare `Literal["dog"]` fails at import with `Column 'type' on class DogAutoModel conflicts with existing column 'animal.type'`.

!!! note "Pyright reports an override error"
    Pyright treats a mutable field's type as invariant, so narrowing an inherited field trips `reportIncompatibleVariableOverride`. No base declaration avoids this - `str`, the full `Literal["dog", "cat"]` union, and a `StrEnum` all report it - so suppress the rule per declaration as above, or disable it for your models module. This is a type checker limitation rather than a SQLCrucible one, and `ty` does not report it.

## Polymorphic Round-Trip

When using inheritance, `from_sa_model()` automatically returns the correct subclass:

```python
dog_sa = Dog.__sqlalchemy_type__(id=uuid7(), name="Fido", type="dog", bones_chewed=42)

# Load via the base class — returns Dog, not Animal
animal = Animal.from_sa_model(dog_sa)
assert isinstance(animal, Dog)
assert animal.bones_chewed == 42
```

This works because SQLCrucible inspects the polymorphic identity to determine which entity class to instantiate.
