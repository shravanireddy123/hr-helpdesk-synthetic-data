"""The whole generation pipeline in one function (used by __main__ and the tests)."""
import random

from faker import Faker

from .anomalies import CHANGED_TABLES, inject_anomalies
from .config import Scale
from .master_data import build_master_data
from .messages import build_messages
from .sla import build_sla
from .tickets import build_tickets


def generate(scale: Scale, seed: int) -> tuple[dict, dict]:
    """Return (tables, truth). `truth` holds ground_truth and expected_decisions."""
    rng = random.Random(seed)            # the ONLY source of randomness
    fake = Faker("en_IN")
    fake.seed_instance(seed)

    tables = build_master_data(rng, fake, scale)
    tables.update(build_tickets(rng, tables["employee"], scale))
    msg = build_messages(rng, tables, tables, scale)
    tables["message"] = msg["message"]
    tables["message_citation"] = msg["message_citation"]
    tables["ticket_status_event"] = sorted(
        tables["ticket_status_event"] + msg["new_events"], key=lambda e: e["event_id"])
    tables.update(build_sla(tables))     # derived: no rng; adds escalations

    anomalies = inject_anomalies(rng, tables)        # corrupt LAST, label everything
    tables.update({name: anomalies[name] for name in CHANGED_TABLES})
    truth = {"ground_truth": anomalies["ground_truth"],
             "expected_decisions": anomalies["expected_decisions"]}
    return tables, truth