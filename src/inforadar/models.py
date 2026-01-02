
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True)
    guid = Column(String, unique=True, nullable=False, index=True)
    link = Column(String, nullable=False)
    title = Column(String, nullable=False)
    published_date = Column(DateTime, nullable=False)
    source = Column(String, nullable=True)

    status_read = Column(Boolean, default=False, nullable=False)
    status_interesting = Column(Boolean, default=False, nullable=False)

    content_md = Column(String, nullable=True)  # Normalized Markdown content
    comments_data = Column(JSON, default=[], nullable=False)  # List of comments

    extra_data = Column(JSON, default={}, nullable=False)

    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:30]}...', status_read={self.status_read})>"


class Setting(Base):
    __tablename__ = 'settings'

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    type = Column(String, nullable=False, default='string') # 'string', 'integer', 'date', 'boolean', 'list', 'custom'
    description = Column(String, nullable=True)

    def __repr__(self):
        return f"<Setting(key='{self.key}', value='{self.value}', type='{self.type}')>"


class SettingListItem(Base):
    __tablename__ = 'setting_list_items'

    id = Column(Integer, primary_key=True)
    setting_key = Column(String, nullable=False)  # References the parent setting key
    item_index = Column(Integer, nullable=False)  # Position in the list
    item_value = Column(String, nullable=False)  # The actual value of the list item

    __mapper_args__ = {
        'confirm_deleted_rows': False  # Prevents warning about bulk deletes
    }

    def __repr__(self):
        return f"<SettingListItem(setting_key='{self.setting_key}', index={self.item_index}, value='{self.item_value}')>"


class SettingCustomField(Base):
    __tablename__ = 'setting_custom_fields'

    id = Column(Integer, primary_key=True)
    setting_key = Column(String, nullable=False)  # References the parent setting key
    field_name = Column(String, nullable=False)   # Name of the custom field (e.g., 'id', 'slug')
    field_value = Column(String, nullable=False)  # Value of the custom field

    def __repr__(self):
        return f"<SettingCustomField(setting_key='{self.setting_key}', field_name='{self.field_name}', value='{self.field_value}')>"
