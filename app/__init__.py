"""Package init — installs the constraint naming convention.

SQLAlchemy resolves a constraint's name when the constraint is *attached* to its
Table, i.e. while the model class body runs, so the convention has to be on
SQLModel.metadata before app/models.py is imported. This module is the only
place guaranteed to run first: importing anything under `app.` imports `app`.

What this actually buys, on this schema: deterministic primary- and foreign-key
names (`pk_phrase`, `fk_attempt_user_id_app_user`) instead of dialect-generated
ones, so a future migration can `op.drop_constraint()` by name without looking
it up in psql. The `ix` template matches SQLAlchemy's own default, and `uq`
never fires — every unique field here is also indexed, which renders as a single
CREATE UNIQUE INDEX rather than a separate UNIQUE constraint.
"""

from sqlmodel import SQLModel

SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    # Note: this template raises for an *unnamed* CheckConstraint. Nothing here
    # produces one (the Difficulty enum uses create_constraint=False), but a
    # future sa.Enum(..., create_constraint=True) would need an explicit name=.
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
