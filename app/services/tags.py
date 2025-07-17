# services/tags.py

from app.models import Tag
from app import db


class TagService:
    @staticmethod
    def rename_tag(user_id: int, tag_id: int, new_name: str) -> tuple[bool, str | None]:
        tag = Tag.query.filter_by(id=tag_id, user_id=user_id).first()
        if not tag:
            return False, "Tag not found."
        # Optional: Uniqueness check
        if Tag.query.filter_by(user_id=user_id, name=new_name).first():
            return False, "Tag name must be unique."
        tag.name = new_name.strip()
        db.session.commit()
        return True, None

    @staticmethod
    def delete_tag(user_id: int, tag_id: int) -> tuple[bool, str | None]:
        tag = Tag.query.filter_by(id=tag_id, user_id=user_id).first()
        if not tag:
            return False, "Tag not found."
        db.session.delete(tag)
        db.session.commit()
        return True, None
