"""Store the DigitalOcean temporary tournament URL.

Revision ID: 9d9b7d75c34a
Revises: 2bf32bd5be0c
"""
from alembic import op
import sqlalchemy as sa


revision = '9d9b7d75c34a'
down_revision = '2bf32bd5be0c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('apps', sa.Column('temporary_url', sa.String(512), nullable=True))


def downgrade():
    op.drop_column('apps', 'temporary_url')
