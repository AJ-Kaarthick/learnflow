"""revision data model

Revision ID: 74eb271ec556
Revises: 505909c1ba21
Create Date: 2026-09-19 13:30:00.000000

V3 Milestone 2 Phase 3: Persistent Revision Data Model.
Adds revision_sessions, revision_session_documents, revision_questions,
and revision_attempts tables with constraints, indexes, and cascades.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74eb271ec556'
down_revision: Union[str, None] = '505909c1ba21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. revision_sessions
    op.create_table(
        'revision_sessions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('owner_type', sa.String(), nullable=False),
        sa.Column('owner_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('revision_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_revision_sessions_owner_id'), ['owner_id'], unique=False)

    # 2. revision_session_documents
    op.create_table(
        'revision_session_documents',
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['revision_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('session_id', 'document_id')
    )
    with op.batch_alter_table('revision_session_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_revision_session_documents_document_id'), ['document_id'], unique=False)

    # 3. revision_questions
    op.create_table(
        'revision_questions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('question_type', sa.String(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('correct_answer', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('source_document_id', sa.String(), nullable=True),
        sa.Column('source_chunk_id', sa.String(), nullable=True),
        sa.Column('evidence_snippet', sa.Text(), nullable=True),
        sa.Column('evidence_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['revision_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('revision_questions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_revision_questions_session_id'), ['session_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_revision_questions_source_document_id'), ['source_document_id'], unique=False)

    # 4. revision_attempts
    op.create_table(
        'revision_attempts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('question_id', sa.String(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('submitted_answer', sa.Text(), nullable=False),
        sa.Column('is_correct', sa.Boolean(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('evaluation_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['question_id'], ['revision_questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['revision_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id', 'attempt_number', name='uq_revision_attempts_question_attempt')
    )
    with op.batch_alter_table('revision_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_revision_attempts_question_id'), ['question_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_revision_attempts_session_id'), ['session_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('revision_attempts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_revision_attempts_session_id'))
        batch_op.drop_index(batch_op.f('ix_revision_attempts_question_id'))

    op.drop_table('revision_attempts')

    with op.batch_alter_table('revision_questions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_revision_questions_source_document_id'))
        batch_op.drop_index(batch_op.f('ix_revision_questions_session_id'))

    op.drop_table('revision_questions')

    with op.batch_alter_table('revision_session_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_revision_session_documents_document_id'))

    op.drop_table('revision_session_documents')

    with op.batch_alter_table('revision_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_revision_sessions_owner_id'))

    op.drop_table('revision_sessions')
