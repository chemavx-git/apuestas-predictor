import os
import time
import logging
from datetime import datetime
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from sqlalchemy.exc import SQLAlchemyError
from models import SessionLocal, Team, Match, Odds, engine, Base
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Configuración
FD_URL = "https://api.football-data.org/v4/matches"
ODDS_URL = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"
HEADERS_FD = {"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")}
ODDS_KEY = os.getenv("ODDS_API_KEY")


# Decorador de reintentos para llamadas HTTP
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
)
def fetch_json(url, params=None, headers=None):
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def ingest_football_data():
    session = SessionLocal()
    try:
        page = 1
        while True:
            params = {"page": page, "limit": 100}
            data = fetch_json(FD_URL, params=params, headers=HEADERS_FD)
            matches = data.get("matches", [])
            if not matches:
                break

            for m in matches:
                # Equipos
                for side in ("homeTeam", "awayTeam"):
                    team_name = m[side]["name"]
                    team = session.query(Team).filter_by(name=team_name).first()
                    if not team:
                        team = Team(name=team_name)
                        session.add(team)
                        session.commit()
                # Partidos
                ext_id = m["id"]
                if not session.query(Match).filter_by(external_id=ext_id).first():
                    match = Match(
                        external_id=ext_id,
                        utc_date=datetime.fromisoformat(
                            m["utcDate"].replace("Z", "+00:00")
                        ),
                        home_team_id=session.query(Team)
                        .filter_by(name=m["homeTeam"]["name"])
                        .one()
                        .id,
                        away_team_id=session.query(Team)
                        .filter_by(name=m["awayTeam"]["name"])
                        .one()
                        .id,
                        competition=m["competition"]["name"],
                    )
                    session.add(match)
                    session.commit()
            page += 1
            time.sleep(1)  # para no superar límites

    except Exception as e:
        logging.error(f"Error ingestando Football-Data: {e}")
    finally:
        session.close()


def ingest_odds_data():
    session = SessionLocal()
    try:
        params = {
            "apiKey": ODDS_KEY,
            "regions": "eu",
            "markets": "h2h",
            "prematch": "true",
        }
        odds_list = fetch_json(ODDS_URL, params=params)
        for o in odds_list:
            match = session.query(Match).filter_by(external_id=o["id"]).first()
            if not match:
                continue
            for site in o.get("bookmakers", []):
                for market in site.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        odd = Odds(
                            match_id=match.id,
                            provider=site["title"],
                            market=market["key"],
                            decimal_odds=outcome["price"],
                            fetched_at=datetime.utcnow(),
                        )
                        session.add(odd)
        session.commit()

    except Exception as e:
        logging.error(f"Error ingestando Odds-API: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    ingest_football_data()
    ingest_odds_data()
    logging.info("Ingesta completada.")
