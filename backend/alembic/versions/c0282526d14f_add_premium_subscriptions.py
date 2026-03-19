"""add premium subscriptions

Revision ID: c0282526d14f
Revises: a80d04ce5aeb
Create Date: 2026-03-19 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c0282526d14f"
down_revision = "a80d04ce5aeb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "premium_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("access_source", sa.String(length=20), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=120), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True),
        sa.Column("stripe_checkout_session_id", sa.String(length=120), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_premium_subscriptions_user_id"), "premium_subscriptions", ["user_id"], unique=True)
    op.create_index(op.f("ix_premium_subscriptions_status"), "premium_subscriptions", ["status"], unique=False)
    op.create_index(op.f("ix_premium_subscriptions_access_source"), "premium_subscriptions", ["access_source"], unique=False)
    op.create_index(op.f("ix_premium_subscriptions_stripe_customer_id"), "premium_subscriptions", ["stripe_customer_id"], unique=False)
    op.create_index(op.f("ix_premium_subscriptions_stripe_subscription_id"), "premium_subscriptions", ["stripe_subscription_id"], unique=False)
    op.create_index(op.f("ix_premium_subscriptions_stripe_checkout_session_id"), "premium_subscriptions", ["stripe_checkout_session_id"], unique=False)
    op.create_index(op.f("ix_premium_subscriptions_current_period_end"), "premium_subscriptions", ["current_period_end"], unique=False)
    op.create_index(op.f("ix_premium_subscriptions_created_at"), "premium_subscriptions", ["created_at"], unique=False)
    op.create_index(op.f("ix_premium_subscriptions_updated_at"), "premium_subscriptions", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_premium_subscriptions_updated_at"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_created_at"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_current_period_end"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_stripe_checkout_session_id"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_stripe_subscription_id"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_stripe_customer_id"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_access_source"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_status"), table_name="premium_subscriptions")
    op.drop_index(op.f("ix_premium_subscriptions_user_id"), table_name="premium_subscriptions")
    op.drop_table("premium_subscriptions")
