"""create schemas

Revision ID: 7f1be83ab61c
Revises: 
Create Date: 2020-12-03 10:15:03.256592

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f1be83ab61c'
down_revision = None
branch_labels = None
depends_on = None

def schema_command(base: str):
    connection = op.get_bind()
    schema_lst = ['so_ana_analysis',
                  'so_ana_doc_worker',
                  'so_ana_management',
                  'so_ana_logging']
    for schema in schema_lst:
        connection.execute(f'{base} {schema}')

def upgrade():
    schema_command('CREATE SCHEMA')

def downgrade():
    schema_command('DROP SCHEMA')
