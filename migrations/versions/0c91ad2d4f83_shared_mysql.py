"""Persist tenant ownership and new-booking pricing; leave old rows dedicated.

Revision ID: 0c91ad2d4f83
Revises: 2bf32bd5be0c
"""

from alembic import op
import sqlalchemy as sa

revision = "0c91ad2d4f83"
down_revision = "2bf32bd5be0c"
branch_labels = None
depends_on = None

FIELDS = [
    ("database_mode", sa.String(16)),
    ("shared_cluster_id", sa.String(36)),
    ("shared_tenant", sa.String(26)),
    ("cloud_app_id", sa.String(36)),
    ("tournament_start_date", sa.Date()),
    ("pricing_version", sa.String(32)),
    ("amount_paid_cents", sa.Integer()),
    ("checkout_key", sa.String(32)),
    ("stripe_charge_id", sa.String(64)),
    ("parent_id", sa.Integer()),
    ("provisioning_until", sa.DateTime()),
]


def upgrade():
    for name, kind in FIELDS:
        op.add_column("apps", sa.Column(name, kind, nullable=True))
    op.create_index("uq_apps_shared_tenant", "apps", ["shared_tenant"], unique=True)
    op.create_index("uq_apps_checkout_key", "apps", ["checkout_key"], unique=True)
    op.create_foreign_key("fk_apps_parent_id", "apps", "apps", ["parent_id"], ["id"])


def downgrade():
    count = (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM apps WHERE database_mode = 'shared'"))
        .scalar()
    )
    if count:
        raise RuntimeError(
            "Retain ownership metadata while shared tournament records exist"
        )
    op.drop_constraint("fk_apps_parent_id", "apps", type_="foreignkey")
    op.drop_index("uq_apps_checkout_key", table_name="apps")
    op.drop_index("uq_apps_shared_tenant", table_name="apps")
    for name, _ in reversed(FIELDS):
        op.drop_column("apps", name)
