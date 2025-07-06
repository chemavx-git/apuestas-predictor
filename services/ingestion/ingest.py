import os
import logging
from datetime import datetime
import requests
from sqlalchemy.exc import SQLAlchemyError
from models import SessionLocal, Team, Match, Odds, Base, engine

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Usamos v4 de Football-Data.org
API_BASE          = "https://api.football-data.org/v4"
COMPETITION_CODE  = "PL"   # Premier League

def create_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas o verificadas.")

def ingest_teams():
    session = SessionLocal()
    url = f"{API_BASE}/competitions/{COMPETITION_CODE}/teams"
    try:
        resp = requests.get(
            url,
            headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")}
        )
        resp.raise_for_status()
        teams = resp.json().get("teams", [])
        logger.info(f"Recibidos {len(teams)} equipos de {url}")

        inserted = 0
        for t in teams:
            obj = Team(id=t["id"], name=t["name"])
            session.merge(obj)
            inserted += 1
        session.commit()
        logger.info(f"Insertados {inserted} equipos en la BD")
    except requests.RequestException as e:
        logger.error(f"Error solicitando equipos: {e}")
    except SQLAlchemyError as e:
        logger.error(f"Error al insertar equipos en BD: {e}")
        session.rollback()
    finally:
        session.close()

def ingest_matches():
    session = SessionLocal()
    url = f"{API_BASE}/competitions/{COMPETITION_CODE}/matches"
    try:
        resp = requests.get(
            url,
            headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")}
        )
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
        logger.info(f"Recibidos {len(matches)} partidos de {url}")

        inserted = 0
        for m in matches:
            obj = Match(
                external_id=str(m["id"]),
                utc_date=m["utcDate"],
                home_team_id=m["homeTeam"]["id"],
                away_team_id=m["awayTeam"]["id"],
                competition=m["competition"]["name"]
            )
            session.merge(obj)
            inserted += 1
        session.commit()
        logger.info(f"Insertados {inserted} partidos en la BD")
    except requests.RequestException as e:
        logger.error(f"Error solicitando partidos: {e}")
    except SQLAlchemyError as e:
        logger.error(f"Error al insertar partidos en BD: {e}")
        session.rollback()
    finally:
        session.close()

def ingest_odds():
    session = SessionLocal()
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"
    try:
        resp = requests.get(
            url,
            params={
                "regions": "uk",
                "markets": "h2h",
                "apiKey": os.getenv("ODDS_API_KEY")
            }
        )
        resp.raise_for_status()
        odds_list = resp.json()
        logger.info(f"Recibidas {len(odds_list)} cuotas de {url}")

        inserted = 0
        for o in odds_list:
            markets = o.get("markets") or []
            if not markets:
                continue
            outcomes = markets[0].get("outcomes") or []
            if not outcomes:
                continue
            outcome = outcomes[0]
            try:
                match_id = int(o.get("match_id"))
            except (TypeError, ValueError):
                continue
            obj = Odds(
                match_id=match_id,
                provider="Odds-API",
                market=markets[0].get("key", "h2h"),
                decimal_odds=outcome.get("price", 0.0),
                fetched_at=datetime.utcnow()
            )
            session.add(obj)
            inserted += 1
        session.commit()
        logger.info(f"Insertadas {inserted} cuotas en la BD")
    except requests.RequestException as e:
        logger.error(f"Error solicitando cuotas: {e}")
        session.rollback()
    except SQLAlchemyError as e:
        logger.error(f"Error al insertar cuotas en BD: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    create_tables()
    ingest_teams()
    ingest_matches()
    ingest_odds()
    logger.info("Ingesta completada.")
