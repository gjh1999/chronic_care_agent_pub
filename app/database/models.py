# app/database/models.py

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.database.connection import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class AuditMixin:
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by = Column(String(36), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    updated_by = Column(String(36), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)


class SysUserModel(AuditMixin, Base):
    __tablename__ = "sys_user"

    user_id = Column(String(36), primary_key=True, default=new_uuid)
    openid = Column(String(128), nullable=True, unique=True, index=True)
    login_name = Column(String(64), nullable=True, unique=True)
    role = Column(String(20), nullable=False, default="patient")
    password_hash = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active", index=True)


class PatientProfileModel(AuditMixin, Base):
    __tablename__ = "patient_profile"

    profile_id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("sys_user.user_id"), nullable=False, unique=True, index=True)
    gender = Column(String(20), nullable=True)
    birth_date = Column(Date, nullable=True)
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    disease_tags = Column(JSON, nullable=False, default=list)
    consent_version = Column(String(32), nullable=True)


class PatientMemoryModel(AuditMixin, Base):
    __tablename__ = "patient_memory"

    user_id = Column(String(36), ForeignKey("sys_user.user_id"), primary_key=True)
    profile = Column(Text, nullable=False, default="# User Profile\n")
    preferences = Column(Text, nullable=False, default="# User Preferences\n")
    care_context = Column(Text, nullable=False, default="# Care Context\n")


class AuthSessionModel(Base):
    __tablename__ = "auth_session"

    session_id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("sys_user.user_id"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class SysParamModel(AuditMixin, Base):
    __tablename__ = "sys_param"

    param_id = Column(String(36), primary_key=True, default=new_uuid)
    param_key = Column(String(100), nullable=False, unique=True)
    param_value = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)
    scope = Column(String(20), nullable=False, default="global")


class HealthObservationModel(AuditMixin, Base):
    __tablename__ = "health_observation"
    __table_args__ = (UniqueConstraint("user_id", "source_event_id", name="uq_observation_source_event"),)

    observation_id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("sys_user.user_id"), nullable=False, index=True)
    metric_type = Column(String(40), nullable=False, index=True)
    value_num = Column(Float, nullable=True)
    value_text = Column(Text, nullable=True)
    unit = Column(String(20), nullable=True)
    systolic_value = Column(Float, nullable=True)
    diastolic_value = Column(Float, nullable=True)
    context = Column(String(40), nullable=True)
    measured_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    source = Column(String(20), nullable=False, default="manual")
    source_event_id = Column(String(100), nullable=True)
    raw_payload = Column(JSON, nullable=True)


class CarePlanModel(AuditMixin, Base):
    __tablename__ = "care_plan"

    plan_id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("sys_user.user_id"), nullable=False, index=True)
    title = Column(String(200), nullable=False, default="健康管理计划")
    summary = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft", index=True)
    revision = Column(Integer, nullable=False, default=1)
    source = Column(String(20), nullable=False, default="ai")
    replaced_by = Column(String(36), ForeignKey("care_plan.plan_id"), nullable=True)


class CarePlanItemModel(AuditMixin, Base):
    __tablename__ = "care_plan_item"

    item_id = Column(String(36), primary_key=True, default=new_uuid)
    plan_id = Column(String(36), ForeignKey("care_plan.plan_id"), nullable=False, index=True)
    item_type = Column(String(30), nullable=False, default="other")
    content = Column(Text, nullable=False)
    schedule_rule = Column(JSON, nullable=True)
    sort_no = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="active")


class ReminderV2Model(AuditMixin, Base):
    __tablename__ = "reminder"

    reminder_id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("sys_user.user_id"), nullable=False, index=True)
    plan_item_id = Column(String(36), ForeignKey("care_plan_item.item_id"), nullable=True)
    title = Column(String(255), nullable=False)
    schedule_rule = Column(JSON, nullable=False, default=dict)
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    channel = Column(String(20), nullable=False, default="in_app")
    status = Column(String(20), nullable=False, default="scheduled", index=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    last_sent_at = Column(DateTime(timezone=True), nullable=True)


class NotificationOutboxModel(Base):
    __tablename__ = "notification_outbox"

    event_id = Column(String(36), primary_key=True, default=new_uuid)
    reminder_id = Column(String(36), ForeignKey("reminder.reminder_id"), nullable=False, index=True)
    dedupe_key = Column(String(128), nullable=False, unique=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    available_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ConversationModel(AuditMixin, Base):
    __tablename__ = "conversation"

    conversation_id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("sys_user.user_id"), nullable=False, index=True)
    title = Column(String(200), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    last_message_at = Column(DateTime(timezone=True), nullable=True)


class ConversationMessageModel(Base):
    __tablename__ = "conversation_message"

    message_id = Column(String(36), primary_key=True, default=new_uuid)
    conversation_id = Column(String(36), ForeignKey("conversation.conversation_id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    structured_data = Column(JSON, nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ConversationCheckpointModel(Base):
    __tablename__ = "conversation_checkpoint"

    checkpoint_id = Column(String(36), primary_key=True, default=new_uuid)
    conversation_id = Column(String(36), ForeignKey("conversation.conversation_id"), nullable=False, index=True)
    interrupt_id = Column(String(36), nullable=False, unique=True, default=new_uuid)
    revision = Column(Integer, nullable=False, default=1)
    state_json = Column(JSON, nullable=False)
    waiting_action = Column(String(40), nullable=False, default="plan_confirmation")
    status = Column(String(20), nullable=False, default="waiting", index=True)
    resume_action = Column(String(20), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    resumed_at = Column(DateTime(timezone=True), nullable=True)


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    audit_id = Column(String(36), primary_key=True, default=new_uuid)
    actor_id = Column(String(36), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    result = Column(String(20), nullable=False, default="success")
    detail = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
