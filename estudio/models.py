from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class Channel(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    theme: str = Field(default="General", max_length=500)
    audience: str = Field(default="Público general", max_length=500)
    language: str = Field(default="es", max_length=12)
    style: str = Field(default="Fotografía cinematográfica natural, luz legible, composición limpia", max_length=2000)
    rules: str = Field(default="", max_length=6000)
    voice: Literal["Spanish-ES-Male-1", "Spanish-ES-Female-1"] = "Spanish-ES-Male-1"
    character_voices: dict[str, str] = Field(default_factory=dict)
    destinations: list[Literal["youtube", "facebook", "tiktok"]] = Field(default_factory=lambda: ["youtube"])


class ProjectInput(BaseModel):
    channel_id: str
    title: str = Field(min_length=1, max_length=150)
    topic: str = Field(default="", max_length=5000)
    script: str = Field(default="", max_length=40000)
    content_type: Literal["fiction", "factual", "opinion"] = "fiction"
    format: Literal["reel", "long", "pilot"] = "reel"
    duration: int = Field(default=120, ge=5, le=900)
    mode: Literal["narration", "characters", "mixed"] = "narration"
    aspect: Literal["9:16", "16:9", "1:1"] = "9:16"
    resolution: Literal["720", "1080"] = "720"
    planner: Literal["manual", "openrouter", "omniroute"] = "manual"
    audio_source: Literal["upload", "riva"] = "upload"
    image_source: Literal["upload", "sdxl", "bridge"] = "upload"
    visual_bible: str = Field(default="", max_length=10000)
    subtitles: bool = True
    burn_subtitles: bool = True
    music_gain: float = Field(default=0.09, ge=0, le=0.3)
    sources: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    parent_id: str | None = None

    @model_validator(mode="after")
    def duration_range(self):
        if self.format == "reel" and not 90 <= self.duration <= 150:
            raise ValueError("Los reels deben durar entre 90 y 150 segundos.")
        if self.format == "long" and not 300 <= self.duration <= 900:
            raise ValueError("Los largos deben durar entre 5 y 15 minutos.")
        if self.format == "pilot" and self.duration > 30:
            raise ValueError("Las pruebas cortas duran como máximo 30 segundos.")
        return self


class SceneInput(BaseModel):
    id: str
    text: str = Field(max_length=8000)
    prompt: str = Field(default="", max_length=5000)
    kind: Literal["image", "clip", "character"] = "image"
    speaker: str = Field(default="narrator", max_length=100)
    start: float = Field(ge=0, le=900)
    end: float = Field(gt=0, le=900)
    source_offset: float = Field(default=0, ge=0, le=900)
    visual_asset: str | None = None
    reference_ids: list[str] = Field(default_factory=list, max_length=8)
    identity_reviewed: bool = False
    lipsync_reviewed: bool = False
    motion: Literal["push", "pull", "still"] = "push"
    transition: Literal["cut", "fade"] = "cut"
    effects: list[dict] = Field(default_factory=list, max_length=15)
    locked: bool = True

    @model_validator(mode="after")
    def interval(self):
        if self.end <= self.start:
            raise ValueError("El final debe ser posterior al inicio.")
        return self


class Review(BaseModel):
    editorial: bool = False
    rights: bool = False
    timing: bool = False
    continuity: bool = False
    playback: bool = False
    factual: bool = False


class BridgeConfig(BaseModel):
    url: str = Field(default="", max_length=500)
    zero_cost_confirmed: bool = False
    evidence_url: str = Field(default="", max_length=1000)
    valid_until: str = Field(default="", max_length=40)
    model: str = Field(default="", max_length=120)
    capabilities: list[Literal["image", "video", "reference", "lipsync"]] = Field(default_factory=list)


class GatewayConfig(BaseModel):
    url: str = "http://127.0.0.1:20128/v1"
    model: str = ""
    zero_cost_confirmed: bool = False
    evidence_url: str = ""
    valid_until: str = ""
    price_per_input_token: float | None = None
    price_per_output_token: float | None = None


class PublishInput(BaseModel):
    platform: Literal["youtube", "facebook", "tiktok"]
    account: str = Field(default="default", pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    when: str | None = None
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    privacy: Literal["private", "unlisted", "public", "SELF_ONLY", "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR"] = "private"
    made_for_kids: bool = False
    ai_generated: bool = True
    authorize: bool = False
