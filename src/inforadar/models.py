
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Article(Base):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True)
    guid = Column(String, unique=True, nullable=False, index=True)
    link = Column(String, nullable=False)
    title = Column(String, nullable=False)
    published_date = Column(DateTime, nullable=False)
    
    status_read = Column(Boolean, default=False, nullable=False)
    status_interesting = Column(Boolean, default=False, nullable=False)
    
    content_md = Column(String, nullable=True)  # Normalized Markdown content
    comments_data = Column(JSON, default=[], nullable=False)  # List of comments
    
    extra_data = Column(JSON, default={}, nullable=False)

    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title[:30]}...', status_read={self.status_read})>"
