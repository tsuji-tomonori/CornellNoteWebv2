from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Task(BaseModel):
    id: UUID = Field(description="項目を一意に識別するUUID")
    text: str = Field(min_length=1, max_length=500, description="アクションの内容")
    done: bool = Field(default=False, description="アクションの完了状態")
    due: date | None = Field(default=None, description="アクションの期日。未指定はnull")


class NoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200, pattern=r"\S", description="ノートのタイトル")
    group: str = Field(
        default="未分類",
        min_length=1,
        max_length=80,
        pattern=r"\S",
        description="科目やコレクションの分類名",
    )
    cue: str = Field(default="", max_length=20000, description="問い・キーワード欄")
    content: str = Field(default="", max_length=80000, description="ノート本文")
    summary: str = Field(default="", max_length=20000, description="学びを要約するまとめ欄")
    tasks: list[Task] = Field(
        default_factory=list[Task], max_length=100, description="チェックリストのアクション一覧"
    )

    @field_validator("tasks")
    @classmethod
    def unique_tasks(cls, tasks: list[Task]) -> list[Task]:
        if len({task.id for task in tasks}) != len(tasks):
            raise ValueError("同じノート内でタスクIDを重複させることはできません")
        return tasks


class TaskOverview(Task):
    note_id: UUID = Field(description="タスクが属するノートの識別子")
    title: str = Field(description="所属ノートの題名")
    group_name: str = Field(description="所属ノートの分類名")


class NoteUpdate(NoteInput):
    version: int = Field(ge=1, description="更新前の版番号。競合検知に使用する")


class Note(NoteInput):
    id: UUID = Field(description="項目を一意に識別するUUID")
    version: int = Field(description="保存されたノートの版番号")
    updated_at: datetime = Field(description="最終更新日時")


class Share(BaseModel):
    token: str = Field(description="期限付き共有リンクのトークン。DBにはハッシュのみ保存する")
    expires_at: datetime = Field(description="共有リンクの有効期限")


class Login(BaseModel):
    username: str = Field(pattern="^(alice|bob)$", description="ローカル検証用のユーザー名")
    password: str = Field(description="ローカル検証用のパスワード")


class Token(BaseModel):
    access_token: str = Field(description="署名付きアクセストークン")
