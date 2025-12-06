
from sqlalchemy import create_engine, inspect, func
from sqlalchemy.orm import sessionmaker
from typing import List, Optional
from datetime import datetime

from .models import Base, Article

class Storage:
    def __init__(self, db_url: str = "sqlite:///inforadar.db"):
        self.engine = create_engine(db_url)
        self._Session = sessionmaker(bind=self.engine)

    def init_db(self):
        """Creates all tables in the database based on the models."""
        Base.metadata.create_all(self.engine)

    def add_or_update_articles(self, articles: List[Article]) -> dict:
        """
        Adds new articles or updates metadata for existing ones.
        Returns: {'added': int, 'updated': int}
        """
        if not articles:
            return {'added': 0, 'updated': 0}

        new_guids = {article.guid for article in articles}
        
        with self._Session() as session:
            # Get existing articles
            existing_articles = session.query(Article).filter(Article.guid.in_(new_guids)).all()
            existing_map = {a.guid: a for a in existing_articles}
            
            added_count = 0
            updated_count = 0
            
            for article in articles:
                if article.guid in existing_map:
                    # Update existing article's metadata
                    existing_article = existing_map[article.guid]
                    existing_article.extra_data = article.extra_data
                    # Ensure source is set if it was missing (migration)
                    if not existing_article.source and article.source:
                        existing_article.source = article.source
                    updated_count += 1
                else:
                    # Add new article
                    session.add(article)
                    added_count += 1
            
            session.commit()
            return {'added': added_count, 'updated': updated_count}

    def get_articles(self, read: Optional[bool] = None, interesting: Optional[bool] = None, source: Optional[str] = None) -> List[Article]:
        """
        Gets articles from the database based on their status.
        
        :param read: The read status of the articles to fetch. If None, fetches all.
        :param interesting: If provided, filters by the interesting status.
        :param source: If provided, filters by the source.
        """
        with self._Session() as session:
            query = session.query(Article)
            
            if read is not None:
                query = query.filter(Article.status_read == read)
            
            if interesting is not None:
                query = query.filter(Article.status_interesting == interesting)
            
            if source:
                query = query.filter(Article.source == source)
            
            return query.order_by(Article.published_date.desc()).all()

    def update_article_status(self, article_id: int, read: Optional[bool] = None, interesting: Optional[bool] = None) -> Optional[Article]:
        """
        Updates the status of a single article by its ID.
        """
        with self._Session() as session:
            article = session.query(Article).filter(Article.id == article_id).first()
            
            if not article:
                return None

            if read is not None:
                article.status_read = read
            
            if interesting is not None:
                article.status_interesting = interesting
            
            session.commit()
            return article

    def get_last_article_date(self, hub: str) -> Optional[datetime]:
        """Gets the most recent article's publication date for a specific hub."""
        # This is a simplified version for the MVP. A real implementation
        # would filter by hub, probably using a tag in the extra_data.
        with self._Session() as session:
            latest_date = session.query(func.max(Article.published_date)).scalar()
            return latest_date

    def get_articles_for_refresh(
        self, 
        after_date: datetime, 
        read: Optional[bool] = None
    ) -> List[Article]:
        """
        Gets articles published after a certain date for metadata refresh.
        Optionally filters by read status.
        """
        with self._Session() as session:
            query = session.query(Article).filter(Article.published_date > after_date)
            
            if read is not None:
                query = query.filter(Article.status_read == read)
            
            return query.order_by(Article.published_date.desc()).all()

    def update_article_metadata(self, article_id: int, extra_data: dict) -> bool:
        """
        Updates only the extra_data field for an article.
        Returns True if successful, False if article not found.
        """
        with self._Session() as session:
            article = session.query(Article).filter(Article.id == article_id).first()
            
            if not article:
                return False
            
            article.extra_data = extra_data
            session.commit()
            return True

    def get_article_count_by_source(self, source_name: str) -> int:
        """Gets the total number of articles for a specific source."""
        with self._Session() as session:
            return session.query(func.count(Article.id)).filter(Article.source == source_name).scalar() or 0

    def get_latest_article_date_by_source(self, source_name: str) -> Optional[datetime]:
        """Gets the most recent article's publication date for a specific source."""
        with self._Session() as session:
            return session.query(func.max(Article.published_date)).filter(Article.source == source_name).scalar()
