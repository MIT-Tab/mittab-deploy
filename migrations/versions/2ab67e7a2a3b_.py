"""empty message

Revision ID: 2ab67e7a2a3b
Revises: 5ab1f9b9fbfe
Create Date: 2017-07-09 23:01:55.932971

"""

# revision identifiers, used by Alembic.
revision = '2ab67e7a2a3b'
down_revision = '5ab1f9b9fbfe'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('droplets', sa.Column('status', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('droplets', 'status')
    # ### end Alembic commands ###
