
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from typing import List, Optional

from .models import Base, Article

class Storage:
    def __init__(self, db_url: str = "sqlite:///inforadar.db"):
        self.engine = create_engine(db_url)
        self._Session = sessionmaker(bind=self.engine)

    def init_db(self):
        """Creates all tables in the database based on the models."""
        Base.metadata.create_all(self.engine)

    def add_articles(self, articles: List[Article]) -> int:
        """
        Adds a list of Article objects to the database, skipping any that already exist based on their GUID.
        Returns the number of newly added articles.
        """
        if not articles:
            return 0

        new_guids = {article.guid for article in articles}
        
        with self._Session() as session:
            existing_guids = {
                guid[0] for guid in session.query(Article.guid).filter(Article.guid.in_(new_guids))
            }
            
            truly_new_articles = [
                article for article in articles if article.guid not in existing_guids
            ]

            if not truly_new_articles:
                return 0

            session.add_all(truly_new_articles)
            session.commit()
            return len(truly_new_articles)

    def get_articles(self, read: bool, interesting: Optional[bool] = None) -> List[Article]:
        """
        Gets articles from the database based on their status.
        
        :param read: The read status of the articles to fetch.
        :param interesting: If provided, filters by the interesting status.
        """
        with self._Session() as session:
            query = session.query(Article).filter(Article.status_read == read)
            
            if interesting is not None:
                query = query.filter(Article.status_interesting == interesting)
            
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

