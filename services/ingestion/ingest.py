import logging
from models import SessionLocal, Team, Match, Odds, Base, engine
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ingest_teams():
    session = SessionLocal()
    response = requests.get(
        "https://api.football-data.org/v2/teams",
        headers={"X-Auth-Token": os.getenv("FOOTBALL_DATA_TOKEN")}
    )
    teams_data = response.json()
    logger.info(f"Recibidos {len(teams_data)} equipos desde Football-Data.org")
    
    inserted = 0
    for t in teams_data:
        obj = Team(id=t["id"], name=t["name"])
        session.merge(obj)
        inserted += 1
    session.commit()
    logger.info(f"Insertados {inserted} equipos en la BD")
    session.close()

def ingest_matches():
    session = SessionLocal()
    # … tu lógica de paginación …
    matches_data = [...]
    logger.info(f"Recibidos {len(matches_data)} partidos")
    inserted = 0
    for m in matches_data:
        obj = Match(
            external_id=str(m["id"]),  # ya lo tienes como string
            utc_date=m["utcDate"],
            home_team_id=m["homeTeam"]["id"],
            away_team_id=m["awayTeam"]["id"],
            competition=m["competition"]["name"],
        )
        session.merge(obj)
        inserted += 1
    session.commit()
    logger.info(f"Insertados {inserted} partidos en la BD")
    session.close()

def ingest_odds():
    session = SessionLocal()
    # … tu llamada a Odds-API …
    odds_data = [...]
    logger.info(f"Recibidas {len(odds_data)} cuotas desde Odds-API")
    inserted = 0
    for o in odds_data:
        obj = Odds(
            match_id= ...,
            provider="Odds-API",
            market="h2h",
            decimal_odds=o["markets"][0]["outcomes"][0]["price"],
            fetched_at=datetime.utcnow(),
        )
        session.add(obj)
        inserted += 1
    session.commit()
    logger.info(f"Insertadas {inserted} cuotas en la BD")
    session.close()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    ingest_teams()
    ingest_matches()
    ingest_odds()
    logger.info("Ingesta completada.")
