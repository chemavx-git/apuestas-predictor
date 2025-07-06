import os
import logging
from datetime import datetime
import requests
from sqlalchemy.exc import SQLAlchemyError
from models import SessionLocal, Team, Match, Odds, Base, engine

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Endpoints
FD_BASE    = "https://api.football-data.org/v4"
COMP       = "PL"  # Premier League
ODDS_URL   = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

def create_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas o verificadas.")

def ingest_teams():
    session = SessionLocal()
    url = f"{FD_BASE}/competitions/{COMP}/teams"
    try:
        r = requests.get(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        r.raise_for_status()
        teams = r.json().get("teams", [])
        logger.info(f"Recibidos {len(teams)} equipos de Football-Data")
        for t in teams:
            if not session.get(Team, t["id"]):
                session.add(Team(id=t["id"], name=t["name"]))
        session.commit()
    except Exception as e:
        logger.error(f"ingest_teams: {e}")
        session.rollback()
    finally:
        session.close()

def ingest_matches():
    session = SessionLocal()
    url = f"{FD_BASE}/competitions/{COMP}/matches"
    try:
        r = requests.get(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        r.raise_for_status()
        data = r.json().get("matches", [])
        logger.info(f"Recibidos {len(data)} partidos de Football-Data")
        existing = {row[0] for row in session.query(Match.external_id).all()}
        for m in data:
            ext = str(m["id"])
            if ext in existing:
                continue
            session.add(Match(
                external_id=ext,
                utc_date=m["utcDate"],
                home_team_id=m["homeTeam"]["id"],
                away_team_id=m["awayTeam"]["id"],
                competition=m["competition"]["name"],
            ))
        session.commit()
    except Exception as e:
        logger.error(f"ingest_matches: {e}")
        session.rollback()
    finally:
        session.close()

def ingest_odds():
    session = SessionLocal()
    try:
        r = requests.get(ODDS_URL, params={
            "regions": "uk",
            "markets": "h2h",
            "apiKey": os.getenv("ODDS_API_KEY")
        })
        r.raise_for_status()
        odds_list = r.json()
        logger.info(f"Recibidas {len(odds_list)} cuotas de Odds-API")

        # Cargo los equipos y partidos para hacer matching
        teams = session.query(Team).all()
        team_names = [(t.name.lower(), t.id) for t in teams]
        matches = session.query(Match).all()
        match_map = { (m.home_team_id, m.away_team_id): m.id for m in matches }

        inserted = 0
        for o in odds_list:
            home_str = (o.get("home_team") or "").lower()
            away_str = (o.get("away_team") or "").lower()

            # Fuzzy match por substrings
            hid = next((tid for name, tid in team_names
                        if name in home_str or home_str in name), None)
            aid = next((tid for name, tid in team_names
                        if name in away_str or away_str in name), None)
            if not hid or not aid:
                continue

            mid = match_map.get((hid, aid))
            if not mid:
                continue

            for bk in o.get("bookmakers", []):
                for mkt in bk.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    for outcome in mkt.get("outcomes", []):
                        price = outcome.get("price")
                        if price is None:
                            continue
                        session.add(Odds(
                            match_id=mid,
                            provider=bk.get("key", bk.get("title", "Odds-API")),
                            market="h2h",
                            decimal_odds=price,
                            fetched_at=datetime.utcnow()
                        ))
                        inserted += 1

        session.commit()
        logger.info(f"Insertadas {inserted} cuotas en la BD")
    except Exception as e:
        logger.error(f"ingest_odds: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    create_tables()
    ingest_teams()
    ingest_matches()
    ingest_odds()
    logger.info("Ingesta completada.")
