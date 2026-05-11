"""Single-table inheritance rooted at a Pydantic-generic class.

A parameterised intermediate (``Release[SingleDetails]``) that adds
nothing of its own at the SQLAlchemy layer reuses ``Release``'s automodel
rather than minting a fresh one — which would otherwise land as an
identity-less polymorphic intermediate (SQLAlchemy warns) with a
bracket-laden ``__name__`` the stub generator can't emit. Concrete
subclasses that supply their own ``polymorphic_identity`` still get their
own automodels, extending ``ReleaseAutoModel`` directly.
"""

import ast
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sqlcrucible.entity.sa_type import SAType
from sqlcrucible.stubs import generate_stubs

from tests.entity.generic_sti_models import (
    Album,
    AlbumDetails,
    Release,
    Single,
    SingleDetails,
    generic_sti_metadata,
)


def test_parameterised_intermediate_reuses_origin_automodel():
    assert SAType[Release[SingleDetails]] is SAType[Release]
    assert SAType[Release[AlbumDetails]] is SAType[Release]


def test_concrete_subclasses_get_own_automodels_extending_the_root_directly():
    assert SAType[Single] is not SAType[Release]
    assert SAType[Album] is not SAType[Release]
    assert issubclass(SAType[Single], SAType[Release])
    assert issubclass(SAType[Album], SAType[Release])
    # No bracket-named intermediate sitting between subclass and root — so
    # SQLAlchemy sees a clean STI chain (abstract root, concrete leaves)
    # rather than an identity-less polymorphic middle class.
    assert SAType[Single].__mro__[1] is SAType[Release]
    assert SAType[Album].__mro__[1] is SAType[Release]


@pytest.fixture
def engine():
    SAType[Single]
    SAType[Album]
    engine = create_engine("sqlite:///:memory:")
    generic_sti_metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_subclasses_round_trip_with_their_parameterised_payload_type(engine):
    """Persist a ``Single`` and an ``Album`` (two concrete subclasses of
    the same generic STI root), query them back, and get instances of the
    right subclass whose ``details`` JSON column has been re-validated to
    that subclass's parameterised Pydantic type — ``SingleDetails`` /
    ``AlbumDetails`` — not the raw stored dict."""
    with Session(engine) as session:
        session.add(
            Single(details=SingleDetails(a_side="Heroes", b_side="V-2 Schneider")).to_sa_model()
        )
        session.add(
            Album(
                details=AlbumDetails(track_titles=["Speed of Life", "Breaking Glass"])
            ).to_sa_model()
        )
        session.commit()

        singles = session.execute(select(SAType[Single])).scalars().all()
        albums = session.execute(select(SAType[Album])).scalars().all()

    [single] = [Single.from_sa_model(r) for r in singles]
    assert isinstance(single.details, SingleDetails)
    assert single.details.a_side == "Heroes"
    assert single.details.b_side == "V-2 Schneider"
    assert single.kind == "single"

    [album] = [Album.from_sa_model(r) for r in albums]
    assert isinstance(album.details, AlbumDetails)
    assert album.details.track_titles == ["Speed of Life", "Breaking Glass"]
    assert album.kind == "album"


def test_polymorphic_query_through_root_dispatches_to_subclass(engine):
    with Session(engine) as session:
        session.add(
            Single(details=SingleDetails(a_side="Heroes", b_side="V-2 Schneider")).to_sa_model()
        )
        session.commit()

        row = session.execute(select(SAType[Release])).scalar_one()

    assert isinstance(row, SAType[Single])


def test_stub_generation_is_well_formed(tmp_path: Path):
    """No bracket-named automodel class is created, so the generated
    stubs contain no class whose name has ``[`` ``]``; the parameterised
    intermediates get no ``SAType`` overload of their own (the origin's
    covers them); and every ``.pyi`` parses as valid Python."""
    generate_stubs(["tests.entity.generic_sti_models"], output_dir=str(tmp_path))

    pyi_files = list(tmp_path.rglob("*.pyi"))
    assert pyi_files, "expected generated .pyi files"

    for pyi in pyi_files:
        source = pyi.read_text()
        # A bracket-named automodel would appear as e.g. `SingleDetails]AutoModel`;
        # a parameterised-generic overload would reference `Release[SingleDetails]`.
        assert "]AutoModel" not in source, f"{pyi} has a bracket-named automodel"
        assert "Release[" not in source, f"{pyi} references a parameterised generic"
        ast.parse(source, filename=str(pyi))  # SyntaxError on malformed output

    sa_type_pyi = (tmp_path / "sqlcrucible" / "entity" / "sa_type.pyi").read_text()
    # The concrete subclasses and the (abstract) origin do get overloads.
    assert "tests.entity.generic_sti_models.Single]" in sa_type_pyi
    assert "tests.entity.generic_sti_models.Album]" in sa_type_pyi
    assert "tests.entity.generic_sti_models.Release]" in sa_type_pyi
