import os
import logging
from datetime import datetime
import requests
from sqlalchemy.exc import SQLAlchemyError
from models import SessionLocal, Team, Match, Odds, Base, engine

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Football-Data.org v4 y Odds-API v4
FD_BASE = "https://api.football-data.org/v4"
COMPETITION = "PL"
ODDS_URL   = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

def create_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas o verificadas.")

def ingest_teams():
    session = SessionLocal()
    url = f"{FD_BASE}/competitions/{COMPETITION}/teams"
    try:
        resp = requests.get(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        resp.raise_for_status()
        teams = resp.json().get("teams", [])
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
    url = f"{FD_BASE}/competitions/{COMPETITION}/matches"
    try:
        resp = requests.get(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        resp.raise_for_status()
        data = resp.json().get("matches", [])
        logger.info(f"Recibidos {len(data)} partidos de Football-Data")
        existing = {m.external_id for (m.external_id,) in session.query(Match.external_id).all()}
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
        resp = requests.get(ODDS_URL, params={
            "regions": "uk",
            "markets": "h2h",
            "apiKey": os.getenv("ODDS_API_KEY")
        })
        resp.raise_for_status()
        odds_list = resp.json()
        logger.info(f"Recibidas {len(odds_list)} cuotas de Odds-API")

        # Cache de equipos y partidos en memoria para matching por nombre
        teams_map = {t.name: t.id for t in session.query(Team).all()}
        matches_map = {}
        for pm in session.query(Match).all():
            key = (pm.home_team_id, pm.away_team_id)
            matches_map[key] = pm.id

        inserted = 0
        for o in odds_list:
            home = o.get("home_team")
            away = o.get("away_team")
            hid = teams_map.get(home)
            aid = teams_map.get(away)
            if not hid or not aid:
                continue
            mid = matches_map.get((hid, aid))
            if not mid:
                continue

            for bk in o.get("bookmakers", []):
                for mkt in bk.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    for outcome in mkt.get("outcomes", []):
                        price = outcome.get("price") or outcome.get("priceDecimal")
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
