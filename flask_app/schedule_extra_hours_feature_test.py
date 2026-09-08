"""Tests locaux de la règle des heures supplémentaires, sans connexion à la base active."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from utils import schedule_extra_hours


assert schedule_extra_hours(10, 18) == 0
assert schedule_extra_hours(18, 18) == 0
assert schedule_extra_hours(22, 18) == 4
assert schedule_extra_hours("22", "18") == 4
assert schedule_extra_hours(None, 18) == 0

print("schedule_extra_hours_feature_test: OK")
