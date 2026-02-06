# API Reference

## Core Classes

### SQLCrucibleBaseModel

::: sqlcrucible.SQLCrucibleBaseModel
    options:
      show_bases: true
      members:
        - to_sa_model
        - from_sa_model
        - __sqlalchemy_type__
        - __sqlalchemy_params__

### SQLCrucibleEntity

::: sqlcrucible.SQLCrucibleEntity
    options:
      show_bases: true
      members:
        - to_sa_model
        - from_sa_model
        - __sqlalchemy_type__
        - __sqlalchemy_params__

### SAType

::: sqlcrucible.SAType
    options:
      show_bases: false

## Annotations

### SQLAlchemyField

::: sqlcrucible.entity.annotations.SQLAlchemyField
    options:
      show_bases: false

### ExcludeSAField

::: sqlcrucible.entity.annotations.ExcludeSAField
    options:
      show_bases: false

### ConvertToSAWith

::: sqlcrucible.entity.annotations.ConvertToSAWith
    options:
      show_bases: false

### ConvertFromSAWith

::: sqlcrucible.entity.annotations.ConvertFromSAWith
    options:
      show_bases: false

## Fields

### readonly_field

::: sqlcrucible.entity.descriptors.readonly_field
    options:
      show_bases: false

## Utilities

### lazyproperty

::: sqlcrucible.entity.core.lazyproperty
    options:
      show_bases: false
