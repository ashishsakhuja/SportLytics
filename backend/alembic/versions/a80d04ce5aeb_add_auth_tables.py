"""add auth tables

Revision ID: a80d04ce5aeb
Revises: b8e0c2d1f712
Create Date: 2026-03-19 14:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'a80d04ce5aeb'
down_revision = 'c61a4f928d10'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=80), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_accounts_created_at'), 'user_accounts', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_accounts_display_name'), 'user_accounts', ['display_name'], unique=False)
    op.create_index(op.f('ix_user_accounts_email'), 'user_accounts', ['email'], unique=True)
    op.create_index(op.f('ix_user_accounts_is_active'), 'user_accounts', ['is_active'], unique=False)
    op.create_index(op.f('ix_user_accounts_updated_at'), 'user_accounts', ['updated_at'], unique=False)

    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auth_sessions_created_at'), 'auth_sessions', ['created_at'], unique=False)
    op.create_index(op.f('ix_auth_sessions_expires_at'), 'auth_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_auth_sessions_last_seen_at'), 'auth_sessions', ['last_seen_at'], unique=False)
    op.create_index(op.f('ix_auth_sessions_revoked_at'), 'auth_sessions', ['revoked_at'], unique=False)
    op.create_index(op.f('ix_auth_sessions_token'), 'auth_sessions', ['token'], unique=True)
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_auth_sessions_user_id'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_token'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_revoked_at'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_last_seen_at'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_expires_at'), table_name='auth_sessions')
    op.drop_index(op.f('ix_auth_sessions_created_at'), table_name='auth_sessions')
    op.drop_table('auth_sessions')

    op.drop_index(op.f('ix_user_accounts_updated_at'), table_name='user_accounts')
    op.drop_index(op.f('ix_user_accounts_is_active'), table_name='user_accounts')
    op.drop_index(op.f('ix_user_accounts_email'), table_name='user_accounts')
    op.drop_index(op.f('ix_user_accounts_display_name'), table_name='user_accounts')
    op.drop_index(op.f('ix_user_accounts_created_at'), table_name='user_accounts')
    op.drop_table('user_accounts')
