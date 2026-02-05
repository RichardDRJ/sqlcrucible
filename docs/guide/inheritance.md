# Inheritance

SQLCrucible supports all three SQLAlchemy inheritance patterns. Each uses `__sqlalchemy_params__` with `__mapper_args__` to configure polymorphism.

## Single Table Inheritance

All subclasses share one table with a discriminator column:

```python
from typing import Annotated
from uuid import UUID, uuid4
from pydantic import Field
from sqlalchemy import String
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible.entity.annotations import ExcludeSAField

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__tablename__": "animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
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
from uuid import UUID, uuid4
from pydantic import Field
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel
from sqlcrucible.entity.annotations import ExcludeSAField

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__tablename__": "animal",
        "__mapper_args__": {"polymorphic_on": "type", "polymorphic_identity": "animal"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))]
    name: str

class Dog(Animal):
    __sqlalchemy_params__ = {
        "__tablename__": "dog",
        "__mapper_args__": {"polymorphic_identity": "dog"},
    }
    id: Annotated[UUID, mapped_column(ForeignKey("animal.id"), primary_key=True)] = Field(default_factory=uuid4)
    bones_chewed: int | None = None
    type: Annotated[str, ExcludeSAField()] = Field(default="dog")
```

## Concrete Table Inheritance

Each subclass is a completely independent table:

```python
from typing import Annotated
from uuid import UUID, uuid4
from pydantic import Field
from sqlalchemy import String
from sqlalchemy.orm import mapped_column
from sqlcrucible import SQLCrucibleBaseModel

class Animal(SQLCrucibleBaseModel):
    __sqlalchemy_params__ = {
        "__abstract__": True,
        "__mapper_args__": {"polymorphic_on": "type"},
    }
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))]
    name: str

class Dog(Animal):
    __sqlalchemy_params__ = {
        "__tablename__": "dog",
        "__mapper_args__": {"polymorphic_identity": "dog", "concrete": True},
    }
    # Must redefine ALL columns for concrete table inheritance
    id: Annotated[UUID, mapped_column(primary_key=True)] = Field(default_factory=uuid4)
    type: Annotated[str, mapped_column(String(50))] = Field(default="dog")
    name: str
    bones_chewed: int | None = None
```

!!! warning
    Concrete table inheritance requires redefining ALL columns in each subclass.

## Polymorphic Round-Trip

When using inheritance, `from_sa_model()` automatically returns the correct subclass:

```python
dog_sa = Dog.__sqlalchemy_type__(id=uuid4(), name="Fido", type="dog", bones_chewed=42)

# Load via the base class — returns Dog, not Animal
animal = Animal.from_sa_model(dog_sa)
assert isinstance(animal, Dog)
assert animal.bones_chewed == 42
```

This works because SQLCrucible inspects the polymorphic identity to determine which entity class to instantiate.
