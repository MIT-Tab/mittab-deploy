"""Add email sent flag

Revision ID: 0f771c963caf
Revises: e9d334937ec4
Create Date: 2020-12-25 14:23:28.083343

"""

# revision identifiers, used by Alembic.
revision = '0f771c963caf'
down_revision = 'e9d334937ec4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('droplets', sa.Column('warning_email_sent', sa.Boolean(), nullable=True, default=False))


def downgrade():
    op.drop_column('droplets', 'warning_email_sent')
