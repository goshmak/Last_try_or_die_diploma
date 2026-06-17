"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def table_exists(table_name):
    """Проверка существования таблицы"""
    conn = op.get_bind()
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Включаем расширение UUID (безопасно)
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Создаем таблицу notifications только если её нет
    if not table_exists('notifications'):
        op.create_table(
            'notifications',
            sa.Column('notification_id', sa.Integer(), nullable=False),
            sa.Column('user_id', UUID(as_uuid=False), nullable=False),
            sa.Column('user_type', sa.String(length=50), nullable=False),
            sa.Column('notification_type', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('channel', sa.String(length=50), nullable=True),
            sa.Column('status', sa.String(length=50), server_default='pending', nullable=True),
            sa.Column('metadata', JSONB(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('sent_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('notification_id')
        )
        
        # Создаем индексы для notifications
        op.create_index('idx_notifications_user_id', 'notifications', ['user_id'])
        op.create_index('idx_notifications_created_at', 'notifications', ['created_at'])
        op.create_index('idx_notifications_status', 'notifications', ['status'])
    else:
        print("Table 'notifications' already exists, skipping creation")
    
    # Создаем таблицу user_notification_preferences только если её нет
    if not table_exists('user_notification_preferences'):
        op.create_table(
            'user_notification_preferences',
            sa.Column('user_id', UUID(as_uuid=False), nullable=False),
            sa.Column('user_type', sa.String(length=50), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('vk_id', sa.String(length=100), nullable=True),
            sa.Column('notification_channel', sa.String(length=50), server_default='email', nullable=True),
            sa.Column('new_assignment_enabled', sa.Boolean(), server_default='true', nullable=True),
            sa.Column('deadline_student_enabled', sa.Boolean(), server_default='true', nullable=True),
            sa.Column('deadline_teacher_enabled', sa.Boolean(), server_default='true', nullable=True),
            sa.Column('assignment_checked_enabled', sa.Boolean(), server_default='true', nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.PrimaryKeyConstraint('user_id')
        )
    else:
        print("Table 'user_notification_preferences' already exists, skipping creation")


def downgrade() -> None:
    # Удаляем таблицы только если они созданы миграцией
    # Будьте осторожны с удалением - проверьте, что таблицы пустые или это тестовые данные
    op.drop_table('user_notification_preferences')
    op.drop_table('notifications')