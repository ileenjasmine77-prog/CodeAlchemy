"""Retains the synthetic past incidents into the Hindsight bank.

Run this once before demo.py so the 'after memory' half of the demo has
something real to recall.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent import IncidentResponseAgent
from app.data.synthetic_incidents import SEED_INCIDENTS


def main():
    agent = IncidentResponseAgent()
    print(f"Retaining {len(SEED_INCIDENTS)} past incidents into bank '{agent.memory.bank_id}'"
          f" ({'offline local store' if agent.memory.offline else 'Hindsight Cloud'})...")
    count = agent.seed(SEED_INCIDENTS)
    print(f"Done — {count} incidents retained.")
    agent.close()


if __name__ == "__main__":
    main()
