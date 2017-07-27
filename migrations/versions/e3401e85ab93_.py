"""empty message

Revision ID: e3401e85ab93
Revises: 7796abf5a85a
Create Date: 2017-07-27 18:40:33.509070

"""

# revision identifiers, used by Alembic.
revision = 'e3401e85ab93'
down_revision = '7796abf5a85a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('droplets', sa.Column('branch', sa.String(), nullable=True))
    op.add_column('droplets', sa.Column('clone_url', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('droplets', 'clone_url')
    op.drop_column('droplets', 'branch')
    # ### end Alembic commands ###