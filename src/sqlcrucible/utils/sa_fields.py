from sqlalchemy import inspect
from typing_extensions import get_annotations, Format
from sqlcrucible.entity.field_resolution import _recursively_evaluate_forward_refs
from sqlalchemy.orm import Mapper, CompositeProperty, RelationshipProperty, ColumnProperty
from typing import cast, Any


def sa_field_type(tp: type, field_name: str) -> Any:
    annotations = get_annotations(tp, eval_str=True, format=Format.VALUE)
    if (annotation := annotations.get(field_name)) is not None:
        return _recursively_evaluate_forward_refs(annotation, owner=tp)

    mapper = cast(Mapper[Any], inspect(tp))
    attrs = mapper.attrs
    prop = attrs.get(field_name)
    match prop:
        case ColumnProperty():
            return prop.columns[0].type.python_type
        case RelationshipProperty():
            return prop.entity.class_
        case CompositeProperty():
            return prop.composite_class
        case _:
            raise TypeError(
                f"Could not determine type of SQLAlchemy field {field_name} in SQLAlchemy type {tp}"
            )
