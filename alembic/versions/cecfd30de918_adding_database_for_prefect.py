"""adding database for prefect

Revision ID: cecfd30de918
Revises: 361fde4943a9
Create Date: 2021-07-27 16:30:44.676573

"""
from alembic import op
import sqlalchemy as sa
import psycopg2


# revision identifiers, used by Alembic.
revision = 'cecfd30de918'
down_revision = '361fde4943a9'
branch_labels = None
depends_on = None

def schema_command(base: str):
    connection = op.get_bind()
    db_url = str(connection.engine.url)
    print(db_url)
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    db_lst = ['SO_ANA_PREFECT']
    for db_name in db_lst :
        cur.execute(f'{base} {db_name}')

def upgrade():
    schema_command('CREATE DATABASE')

def downgrade():
    schema_command('DROP DATABASE')