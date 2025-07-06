import os
import logging
from datetime import datetime
import requests
from sqlalchemy.exc import SQLAlchemyError
from models import SessionLocal, Team, Match, Odds, Base, engine

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Endpoints de Football-Data.org v4
API_BASE         = "https://api.football-data.org/v4"
COMPETITION_CODE = "PL"  # Premier League

def create_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas o verificadas.")

def ingest_teams():
    session = SessionLocal()
    url = f"{API_BASE}/competitions/{COMPETITION_CODE}/teams"
    try:
        resp = requests.get(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        resp.raise_for_status()
        teams = resp.json().get("teams", [])
        logger.info(f"Recibidos {len(teams)} equipos de {url}")
        inserted = 0
        for t in teams:
            if not session.get(Team, t["id"]):
                session.add(Team(id=t["id"], name=t["name"]))
                inserted += 1
        session.commit()
        logger.info(f"Insertados {inserted} equipos en la BD")
    except Exception as e:
        logger.error(f"Error en ingest_teams: {e}")
        session.rollback()
    finally:
        session.close()

def ingest_matches():
    session = SessionLocal()
    url = f"{API_BASE}/competitions/{COMPETITION_CODE}/matches"
    try:
        resp = requests.get(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        resp.raise_for_status()
        matches = resp.json().get("matches", [])
        logger.info(f"Recibidos {len(matches)} partidos de {url}")
        existing = {m.external_id for m in session.query(Match.external_id).all()}
        inserted = 0
        for m in matches:
            ext_id = str(m["id"])
            if ext_id in existing:
                continue
            session.add(Match(
                external_id=ext_id,
                utc_date=m["utcDate"],
                home_team_id=m["homeTeam"]["id"],
                away_team_id=m["awayTeam"]["id"],
                competition=m["competition"]["name"],
            ))
            inserted += 1
        session.commit()
        logger.info(f"Insertados {inserted} partidos en la BD")
    except Exception as e:
        logger.error(f"Error en ingest_matches: {e}")
        session.rollback()
    finally:
        session.close()

def ingest_odds():
    session = SessionLocal()
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"
    try:
        resp = requests.get(url, params={
            "regions": "uk",
            "markets": "h2h",
            "apiKey": os.getenv("ODDS_API_KEY")
        })
        resp.raise_for_status()
        odds_list = resp.json()
        logger.info(f"Recibidas {len(odds_list)} cuotas de {url}")

        inserted = 0
        for o in odds_list:
            # Navegar en 'bookmakers' en lugar de 'markets'
            bks = o.get("bookmakers") or []
            if not bks:
                continue
            markets = bks[0].get("markets") or []
            for market in markets:
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    # 'match_id' es el external_id de Match
                    try:
                        ext = str(o["match_id"])
                        match = session.query(Match).filter_by(external_id=ext).first()
                        if not match:
                            continue
                        odds = Odds(
                            match_id=match.id,
                            provider="Odds-API",
                            market="h2h",
                            decimal_odds=outcome.get("price", 0.0),
                            fetched_at=datetime.utcnow()
                        )
                        session.add(odds)
                        inserted += 1
                    except Exception:
                        continue
        session.commit()
        logger.info(f"Insertadas {inserted} cuotas en la BD")
    except Exception as e:
        logger.error(f"Error en ingest_odds: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    create_tables()
    ingest_teams()
    ingest_matches()
    ingest_odds()
    logger.info("Ingesta completada.")
