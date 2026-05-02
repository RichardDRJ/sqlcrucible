"""Tests for composite-backed fields.

A composite field is one Pydantic attribute that decomposes into several
SA columns via :func:`sqlalchemy.orm.composite` and the
``__composite_values__`` protocol. SQLCrucible's two output paths must
agree on the wire format:

* :meth:`to_sa_model` constructs an SA instance whose composite
  descriptor decomposes the value into its underlying columns on
  persist.

* :meth:`to_column_dict` produces a flat ``{column_name: value}`` dict
  usable directly with Core-level bulk inserts, with the same column
  values the composite descriptor would have decomposed into.

The two paths share a single column projection so they can't drift.
"""
