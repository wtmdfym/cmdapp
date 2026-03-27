from pydantic import BaseModel, ConfigDict, model_validator
from typing import Literal, Optional, Any


class BaseItem(BaseModel):
    type: str

    model_config = ConfigDict(extra="forbid")


class DBItem(BaseItem):
    type: str = "db"

    collection: str
    backup: bool = False
    op: Literal["insert", "update", "rename"]

    document: Optional[dict[str, Any]] = None
    update_filter: Optional[dict[str, Any]] = None
    update: Optional[dict[str, Any]] = None
    new_name: Optional[str] = None

    @model_validator(mode="after")
    def verify_op(self):
        if self.op == "insert" and not self.document:
            raise ValueError("insert requires document")
        if self.op == "update" and not (self.update_filter and self.update):
            raise ValueError("update requires filter and update")
        if self.op == "rename" and not self.new_name:
            raise ValueError("rename requires new_name")
        return self


class PrintItem(BaseItem):
    type: str = "print"

    data: dict[str, Any]
