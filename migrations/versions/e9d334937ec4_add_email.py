"""Add email

Revision ID: e9d334937ec4
Revises: 855dac18ad74
Create Date: 2020-12-25 10:52:59.048998

"""

# revision identifiers, used by Alembic.
revision = 'e9d334937ec4'
down_revision = '855dac18ad74'

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('droplets') as batch_op:
        batch_op.add_column(
            sa.Column('email', sa.String(), nullable=True, default='benmuschol@gmail.com')
        )
        batch_op.alter_column('email', nullable=False)


def downgrade():
    op.drop_column('droplets', 'email')
