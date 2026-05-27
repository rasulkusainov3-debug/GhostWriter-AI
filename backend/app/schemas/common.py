from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiMessage(BaseModel):
    ok: bool = True
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class RegisterRequest(BaseModel):
    name: str
    username: str | None = None
    email: str
    password: str
    password_confirm: str | None = None
    plan: str = "free"
    social_links: list[str] = Field(default_factory=list)
    optional_profile: dict[str, Any] = Field(default_factory=dict)


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    name: str | None = None
    niche: str | None = None
    profession: str | None = None
    goal: str | None = None
    tone: str | None = None
    audience: str | None = None
    avoid: str | None = None
    user_values: list[str] | None = None
    platforms: list[str] | None = None
    raw_answers: dict[str, Any] | None = None


class LifecycleConfirmRequest(BaseModel):
    scope: str = Field(pattern="^(profile|audience|all)$")


class InterviewAnswer(BaseModel):
    key: str
    answer: str


class SocialLinksRequest(BaseModel):
    links: list[str]


class ParserRunRequest(BaseModel):
    sources: list[str] = Field(default_factory=lambda: ["rss", "ddg"])
    niche: str | None = None
    execute_legacy: bool = False


class ContentPlanCreate(BaseModel):
    title: str = "Content plan"
    posts_per_week: int = Field(default=5, ge=1, le=14)
    week_start: date | None = None


class ContentPlanItemUpdate(BaseModel):
    platform: str | None = None
    format: str | None = None
    post_idea: str | None = None
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    status: str | None = None


class StatusUpdate(BaseModel):
    status: str


class GeneratePostsRequest(BaseModel):
    use_llm: bool = False
    item_ids: list[UUID] | None = None
    mode: str = "regenerate_full"
    language: str | None = None


class GeneratePostFromTrendRequest(BaseModel):
    use_llm: bool = True
    platform: str | None = None
    format: str | None = None
    language: str | None = None


class GeneratedPostUpdate(BaseModel):
    draft_text: str | None = None
    final_text: str | None = None
    status: str | None = None


class ManualSocialAccountCreate(BaseModel):
    platform: str
    display_name: str
    account_url: str | None = None
    external_account_id: str | None = None


class SchedulePostRequest(BaseModel):
    platform: str
    scheduled_for: datetime
    social_account_id: UUID | None = None
    selected_asset_id: UUID | None = None


class PostMetricsUpsertRequest(BaseModel):
    scheduled_post_id: UUID | None = None
    platform: str | None = None
    metric_date: date
    source: str = "manual"
    impressions: int = Field(default=0, ge=0)
    reach: int = Field(default=0, ge=0)
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    saves: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    reactions: int = Field(default=0, ge=0)
    engagement_rate: float | None = Field(default=None, ge=0)
    raw_metrics: dict[str, Any] = Field(default_factory=dict)


class PostMetricsResponse(BaseModel):
    id: UUID
    user_id: UUID
    generated_post_id: UUID
    scheduled_post_id: UUID | None = None
    platform: str
    metric_date: date
    source: str
    impressions: int
    reach: int
    views: int
    likes: int
    comments: int
    shares: int
    saves: int
    clicks: int
    reactions: int
    engagement_rate: float
    raw_metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None


class ChatMessageRequest(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class GenericRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID | int | str
    created_at: datetime | None = None
