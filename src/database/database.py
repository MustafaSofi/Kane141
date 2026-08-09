"""
ORM for the database
"""

from sqlalchemy import create_engine, Column, Integer, String, func
from sqlalchemy.orm import declarative_base, sessionmaker
import getpass
import os

Base = declarative_base()

class Game(Base):
    __tablename__ = 'games'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    cover = Column(String)
    size = Column(String)
    magnet = Column(String)
    platform = Column(String)
    description = Column(String)
    steam_appid = Column(String)
    torrent_url = Column(String)
    release_name = Column(String)
    date_uploaded = Column(String)
    
    def __init__(self, name, cover, size, magnet, platform, description, steam_appid=None, torrent_url=None, release_name=None, date_uploaded=None):
        self.name = name
        self.cover = cover
        self.size = size
        self.magnet = magnet
        self.platform = platform
        self.description = description
        self.steam_appid = steam_appid
        self.torrent_url = torrent_url
        self.release_name = release_name
        self.date_uploaded = date_uploaded

    def __repr__(self):
        return f"<Game(name={self.name}, cover={self.cover}, size={self.size}, platform={self.platform})>"
    
class GamesInfo(Base):
    __tablename__ = 'games_info'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    cover = Column(String)
    description = Column(String)
    
    def __init__(self, name, cover, description):
        self.name = name
        self.cover = cover
        self.description = description
        

    def __repr__(self):
        return f"<CoversDB(name={self.name}, cover={self.cover}, description={self.description})>"
    

class Database:
    """
    Interface for the database with batch transaction optimizations.
    """
    def __init__(self, db_file):
        self.db_file = db_file
        user_name = getpass.getuser()
        config_path = f"/home/{user_name}/.config/kane141"
        os.makedirs(config_path, exist_ok=True)
        db_file_path = os.path.join(config_path, db_file)
        
        self.engine = create_engine(
            f'sqlite:///{db_file_path}', 
            echo=False,
            connect_args={"check_same_thread": False}
        )
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        Base.metadata.create_all(self.engine)
        self._migrate_schema()

    def _migrate_schema(self):
        """Add columns to existing databases that predate them (create_all
        only creates brand-new tables, it won't alter existing ones)."""
        from sqlalchemy import text
        with self.engine.connect() as conn:
            existing_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(games)"))}
            if "steam_appid" not in existing_cols:
                conn.execute(text("ALTER TABLE games ADD COLUMN steam_appid TEXT"))
                conn.commit()
            if "torrent_url" not in existing_cols:
                conn.execute(text("ALTER TABLE games ADD COLUMN torrent_url TEXT"))
                conn.commit()
            if "release_name" not in existing_cols:
                conn.execute(text("ALTER TABLE games ADD COLUMN release_name TEXT"))
                conn.commit()
            if "date_uploaded" not in existing_cols:
                conn.execute(text("ALTER TABLE games ADD COLUMN date_uploaded TEXT"))
                conn.commit()

            # de-dupe any existing duplicate rows before adding the unique
            # index below, or the index creation itself would fail
            conn.execute(text("""
                DELETE FROM games WHERE torrent_url IS NOT NULL AND id NOT IN (
                    SELECT MIN(id) FROM games
                    WHERE torrent_url IS NOT NULL
                    GROUP BY torrent_url
                )
            """))
            conn.commit()

            # partial unique index: allows any number of NULLs (older rows
            # scraped before torrent_url existed) but makes it impossible
            # for the same torrent to be inserted twice going forward
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_games_torrent_url "
                "ON games(torrent_url) WHERE torrent_url IS NOT NULL"
            ))
            conn.commit()
        
    def add_games_batch(self, game_dicts):
        """Batch insert or update games and metadata in a single transaction."""
        if not game_dicts:
            return

        session = self.Session()
        try:
            # Load existing GamesInfo records into memory for fast lookup
            existing_info = {gi.name.lower(): gi for gi in session.query(GamesInfo).all()}

            # skip anything whose torrent_url is already in the DB -- the
            # partial unique index below is the hard guarantee, but
            # filtering here avoids a batch-killing IntegrityError and
            # keeps the "how many new repacks" count accurate
            existing_urls = {
                r[0] for r in session.query(Game.torrent_url).filter(Game.torrent_url.isnot(None)).all()
            }
            
            games_to_add = []
            info_to_add = []
            seen_urls_this_batch = set()

            for item in game_dicts:
                name = item.get("name", "")
                cover = item.get("cover")
                size = item.get("size", "")
                magnet = item.get("magnet", "")
                platform = item.get("pltfrm", "unknown")
                description = item.get("summary", "")
                steam_appid = item.get("appid")
                torrent_url = item.get("url")
                release_name = item.get("release_name")
                date_uploaded = item.get("date")

                if torrent_url and (torrent_url in existing_urls or torrent_url in seen_urls_this_batch):
                    continue
                if torrent_url:
                    seen_urls_this_batch.add(torrent_url)

                key = name.lower()
                if key not in existing_info:
                    info_obj = GamesInfo(name, cover, description)
                    info_to_add.append(info_obj)
                    existing_info[key] = info_obj
                elif existing_info[key].cover is None:
                    existing_info[key].cover = cover
                    existing_info[key].description = description

                games_to_add.append(
                    Game(
                        name=name,
                        cover=cover,
                        size=size,
                        magnet=magnet,
                        platform=platform,
                        description=description,
                        steam_appid=steam_appid,
                        torrent_url=torrent_url,
                        release_name=release_name,
                        date_uploaded=date_uploaded
                    )
                )

            if info_to_add:
                session.add_all(info_to_add)
            if games_to_add:
                session.add_all(games_to_add)
            
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_game(self, name, cover, size, magnet, platform, description, steam_appid=None):
        self.add_games_batch([{
            "name": name,
            "cover": cover,
            "size": size,
            "magnet": magnet,
            "pltfrm": platform,
            "summary": description,
            "appid": steam_appid
        }])
        
    def get_games(self):
        return self.session.query(Game).all()

    def get_known_torrent_urls(self):
        """Cheap set of every torrent_url already in the DB, for comparing
        against a fresh 1337x listing page without needing to visit each
        torrent's detail page first."""
        rows = self.session.query(Game.torrent_url).filter(Game.torrent_url.isnot(None)).all()
        return {r[0] for r in rows}
    
    def get_game(self, name):
        return self.session.query(Game).filter(Game.name.ilike(f'%{name}%')).all()
    
    def get_library_game(self, name):
        return self.session.query(GamesInfo).filter(GamesInfo.name.ilike(f'%{name}%')).all()
    
    def get_game_by_magnet(self, magnet):
        return self.session.query(Game).filter(Game.magnet == magnet).first()
    
    def get_specific_game(self, name):
        return self.session.query(Game).filter(Game.name == name).first()
    
    def get_randn_games(self, n):
        if n > self.count_games():
            return self.get_games()
        return self.session.query(Game).order_by(func.random()).limit(n).all()
    
    def get_games_page(self, offset, limit):
        return self.session.query(Game).order_by(Game.id).offset(offset).limit(limit).all()
    
    def get_game_page(self, name, offset, limit):
        return self.session.query(Game).filter(Game.name.ilike(f'%{name}%')).order_by(Game.id).offset(offset).limit(limit).all()
    
    def count_game_search(self, name):
        return self.session.query(Game).filter(Game.name.ilike(f'%{name}%')).count()
    
    def delete_game(self, name):
        game = self.get_game(name)
        if game:
            for g in game:
                self.session.delete(g)
            self.session.commit()
        
    def update_game(self, name, cover, size, magnet, platform, description):
        game = self.session.query(Game).filter(Game.name == name).first()
        if game:
            game.cover = cover
            game.size = size
            game.magnet = magnet
            game.platform = platform
            game.description = description
            self.session.commit()
        
    def count_games(self):
        return self.session.query(Game).count()
    
    def _add_game_info(self, name, cover, description):
        cover_obj = GamesInfo(name, cover, description)
        self.session.add(cover_obj)
        self.session.commit()
        
    def _get_game_info(self, name):
        return self.session.query(GamesInfo).filter(GamesInfo.name.ilike(f'%{name}%')).first()
    
    def _update_game_info(self, name, cover, description):
        game_info = self._get_game_info(name)
        if game_info:
            game_info.cover = cover
            game_info.description = description
            self.session.commit()
        
    def close(self):
        self.session.close()
        
    def delete_all(self):
        self.session.query(Game).delete()
        self.session.commit()
