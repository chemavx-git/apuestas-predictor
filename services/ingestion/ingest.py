import os
import logging
import time
from datetime import datetime
import requests
from sqlalchemy.exc import SQLAlchemyError
from models import SessionLocal, Team, Match, Odds, Base, engine

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Endpoints de Football-Data.org v4 y Odds-API v4
FD_BASE      = "https://api.football-data.org/v4"
COMPETITION  = "PL"
ODDS_URL     = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"

# Retries para gestionar rate limits (HTTP 429)
MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos

def request_with_retry(url, headers=None, params=None):
    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp
        if resp.status_code == 429:
            # Rate limited: espera antes de reintentar
            retry_after = resp.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else RETRY_DELAY * attempt
            logger.warning(f"429 en {url}, reintentando en {wait}s (intento {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
            continue
        # Otros errores: lanzar excepción
        resp.raise_for_status()
    return None

def create_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("Tablas creadas o verificadas.")

def ingest_teams():
    session = SessionLocal()
    url = f"{FD_BASE}/competitions/{COMPETITION}/teams"
    try:
        resp = request_with_retry(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        if not resp:
            raise Exception("Límite de peticiones alcanzado en teams")
        teams = resp.json().get("teams", [])
        logger.info(f"Recibidos {len(teams)} equipos de Football-Data")

        inserted = 0
        for t in teams:
            if not session.get(Team, t["id"]):
                session.add(Team(id=t["id"], name=t["name"]))
                inserted += 1
        session.commit()
        logger.info(f"Insertados {inserted} equipos en la BD")
    except Exception as e:
        logger.error(f"ingest_teams: {e}")
        session.rollback()
    finally:
        session.close()

def ingest_matches():
    session = SessionLocal()
    url = f"{FD_BASE}/competitions/{COMPETITION}/matches"
    try:
        resp = request_with_retry(url, headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")})
        if not resp:
            raise Exception("Límite de peticiones alcanzado en matches")
        data = resp.json().get("matches", [])
        logger.info(f"Recibidos {len(data)} partidos de Football-Data")

        existing = {row[0] for row in session.query(Match.external_id).all()}
        inserted = 0
        for item in data:
            ext_id = str(item["id"])
            if ext_id in existing:
                continue
            session.add(Match(
                external_id=ext_id,
                utc_date=item["utcDate"],
                home_team_id=item["homeTeam"]["id"],
                away_team_id=item["awayTeam"]["id"],
                competition=item["competition"]["name"],
            ))
            inserted += 1

        session.commit()
        logger.info(f"Insertados {inserted} partidos en la BD")
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

        # Mapas para matching por nombres de equipo
        teams_map = {t.name: t.id for t in session.query(Team).all()}
        matches_map = {
            (m.home_team_id, m.away_team_id): m.id
            for m in session.query(Match).all()
        }

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
