"""Gestion du budget pour Calv-a-lot.

Version simplifiée : pas de budget AI, juste le suivi du capital
et la mécanique de survie.
"""

import logging

from config.settings import Settings
from app import models

logger = logging.getLogger("calvalot.budget")


class BudgetManager:
    def __init__(self):
        self.settings = Settings

    def initialize(self):
        """Initialise le budget au premier lancement."""
        existing = models.get_budget()
        if existing:
            logger.info(f"Budget existant: {existing['status']} "
                        f"({existing['initial_total_eur']}€)")
            return existing

        budget_id = models.create_budget(
            initial_total_eur=self.settings.INITIAL_BUDGET_EUR,
        )
        logger.info(f"Budget initialisé: {self.settings.INITIAL_BUDGET_EUR}€")
        return models.get_budget()

    def can_trade(self):
        """Vérifie si le follower peut trader.
        Returns (allowed: bool, reason: str).
        """
        budget = models.get_budget()
        if not budget:
            return False, "NO_BUDGET: Budget not initialized"

        if budget["status"] == "DEAD":
            return False, "DEAD: Agent permanently disabled"

        if budget["status"] == "PAUSED":
            return False, "PAUSED: Agent is paused"

        return True, "OK"

    def get_status(self):
        """Status complet du budget pour le dashboard."""
        budget = models.get_budget()
        if not budget:
            return {"status": "UNINITIALIZED"}

        positions = models.get_positions()
        total_deposited = budget.get("total_deposited_eur") or budget["initial_total_eur"]

        return {
            "status": budget["status"],
            "initial_total_eur": budget["initial_total_eur"],
            "total_deposited_eur": total_deposited,
            "positions_count": len([p for p in positions if p["quantity"] > 0]),
            "created_at": budget["created_at"],
        }

    def check_survival(self, total_value_eur):
        """Vérifie si l'agent doit mourir (valeur < minimum)."""
        budget = models.get_budget()
        if not budget or budget["status"] == "DEAD":
            return

        if total_value_eur < self.settings.MIN_BUDGET_EUR:
            models.update_budget_status(budget["id"], "DEAD")
            logger.critical(f"Agent DEAD: {total_value_eur:.2f}€ < {self.settings.MIN_BUDGET_EUR}€")
