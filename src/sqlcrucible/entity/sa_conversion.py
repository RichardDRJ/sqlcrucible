from typing import Any, TypeVar, TYPE_CHECKING

from sqlcrucible._types.annotations import unwrap, types_are_non_parameterised_and_equal
from sqlcrucible.conversion.registry import Converter, ConverterFactory, ConverterRegistry

if TYPE_CHECKING:
    from sqlcrucible.entity.core import SQLCrucibleEntity

_E = TypeVar("_E", bound="SQLCrucibleEntity")


class ToSAModelConverter(Converter[_E, Any]):
    def __init__(self, sqlcrucible_entity: type[_E]):
        self._sqlcrucible_entity = sqlcrucible_entity

    def matches(self, source_tp: type[_E], target_tp: Any) -> bool:
        source_matches_my_entity = types_are_non_parameterised_and_equal(
            source_tp, self._sqlcrucible_entity
        )
        target_matches_source_sa_type = types_are_non_parameterised_and_equal(
            source_tp.__sqlalchemy_type__, target_tp
        )
        return source_matches_my_entity and target_matches_source_sa_type

    def convert(self, source: _E) -> Any:
        return source.to_sa_model()

    def safe_convert(self, source: _E) -> Any:
        return self.convert(source)


class ToSAModelConverterFactory(ConverterFactory[Any, Any]):
    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        from sqlcrucible.entity.core import SQLCrucibleEntity

        stripped_source = unwrap(source_tp)
        if not isinstance(stripped_source, type):
            return False

        return issubclass(
            stripped_source, SQLCrucibleEntity
        ) and types_are_non_parameterised_and_equal(source_tp.__sqlalchemy_type__, target_tp)

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        return ToSAModelConverter(unwrap(source_tp))


class FromSAModelConverter(Converter[_E, Any]):
    def __init__(self, sqlcrucible_entity: type[_E]):
        self._sqlcrucible_entity = sqlcrucible_entity

    def matches(self, source_tp: type[_E], target_tp: Any) -> bool:
        target_matches_my_entity = types_are_non_parameterised_and_equal(
            target_tp, self._sqlcrucible_entity
        )
        source_matches_target_sa_type = types_are_non_parameterised_and_equal(
            target_tp.__sqlalchemy_type__, source_tp
        )
        return target_matches_my_entity and source_matches_target_sa_type

    def convert(self, source: _E) -> Any:
        return self._sqlcrucible_entity.from_sa_model(source)

    def safe_convert(self, source: _E) -> Any:
        return self.convert(source)


class FromSAModelConverterFactory(ConverterFactory[Any, Any]):
    def matches(self, source_tp: Any, target_tp: Any) -> bool:
        from sqlcrucible.entity.core import SQLCrucibleEntity

        stripped_target = unwrap(target_tp)
        if not isinstance(stripped_target, type):
            return False

        return issubclass(
            stripped_target, SQLCrucibleEntity
        ) and types_are_non_parameterised_and_equal(target_tp.__sqlalchemy_type__, source_tp)

    def converter(
        self, source_tp: Any, target_tp: Any, registry: ConverterRegistry
    ) -> Converter[Any, Any] | None:
        return FromSAModelConverter(unwrap(target_tp))
