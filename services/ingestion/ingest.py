import os
import logging
from datetime import datetime
import requests
from sqlalchemy.exc import SQLAlchemyError
from models import SessionLocal, Team, Match, Odds, Base, engine

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas o verificadas.")

def ingest_teams():
    session = SessionLocal()
    try:
        response = requests.get(
            "https://api.football-data.org/v2/teams",
            headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")}
        )
        response.raise_for_status()
        teams_data = response.json().get("teams", [])
        logger.info(f"Recibidos {len(teams_data)} equipos desde Football-Data.org")

        inserted = 0
        for t in teams_data:
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
    try:
        page = 1
        matches_data = []
        while True:
            resp = requests.get(
                f"https://api.football-data.org/v2/matches?page={page}",
                headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")}
            )
            resp.raise_for_status()
            data = resp.json().get("matches", [])
            if not data:
                break
            matches_data.extend(data)
            page += 1

        logger.info(f"Recibidos {len(matches_data)} partidos desde Football-Data.org")

        inserted = 0
        for m in matches_data:
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
    try:
        response = requests.get(
            "https://api.the-odds-api.com/v4/sports/soccer_epl/odds",
            params={
                "regions": "uk",
                "markets": "h2h",
                "apiKey": os.getenv("ODDS_API_KEY")
            }
        )
        response.raise_for_status()
        odds_data = response.json()
        logger.info(f"Recibidas {len(odds_data)} cuotas desde Odds-API")

        inserted = 0
        for o in odds_data:
            market = o["markets"][0]
            outcome = market["outcomes"][0]
            obj = Odds(
                match_id=int(o["match_id"]),
                provider="Odds-API",
                market=market["key"],
                decimal_odds=outcome["price"],
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
