"""Store the forum selection from tournament checkout."""

from alembic import op
import sqlalchemy as sa

revision = "8ce210f763bc"
down_revision = "0c91ad2d4f83"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("apps", sa.Column("forum_mode", sa.String(10), nullable=True))
    op.add_column("apps", sa.Column("forum_selection", sa.String(512), nullable=True))
    op.add_column("apps", sa.Column("forum_announcement_url", sa.String(512), nullable=True))


def downgrade():
    op.drop_column("apps", "forum_announcement_url")
    op.drop_column("apps", "forum_selection")
    op.drop_column("apps", "forum_mode")
