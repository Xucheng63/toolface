"""
Stub for tau2.domains.airline.utils.
Points AIRLINE_DB_PATH to the local db.json.
"""
from pathlib import Path

# db.json should be in the same directory as this file
AIRLINE_DB_PATH = Path(__file__).parent / "db.json"
