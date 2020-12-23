"""deletion date field with default

Revision ID: 855dac18ad74
Revises: 7039ec6b9c23
Create Date: 2020-12-23 11:16:00.490880

"""

# revision identifiers, used by Alembic.
revision = '855dac18ad74'
down_revision = '7039ec6b9c23'

from datetime import date

from alembic import op
import sqlalchemy as sa


def upgrade():
    with op.batch_alter_table('droplets') as batch_op:
        batch_op.add_column(
            sa.Column('deletion_date', sa.Date(), nullable=True, default=date(1970, 1, 1))
        )
        batch_op.alter_column('deletion_date', nullable=False)


def downgrade():
    op.drop_column('droplets', 'deletion_date')
