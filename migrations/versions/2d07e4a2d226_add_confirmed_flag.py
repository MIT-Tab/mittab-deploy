"""Add confirmed flag

Revision ID: 2d07e4a2d226
Revises: 0f771c963caf
Create Date: 2020-12-25 15:35:22.721876

"""

# revision identifiers, used by Alembic.
revision = '2d07e4a2d226'
down_revision = '0f771c963caf'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('droplets', sa.Column('confirmed', sa.Boolean(), nullable=True, default=False))


def downgrade():
    op.drop_column('droplets', 'confirmed')
