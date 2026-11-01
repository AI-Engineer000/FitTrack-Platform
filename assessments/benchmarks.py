"""Provisional general fitness reference bands for matching measurements."""

BENCHMARK_SOURCE = "General Fitness Reference"

BENCHMARKS = {
    "vertical_jump": {
        "unit": "cm",
        "higher_is_better": True,
        "reference": "ACSM Guidelines",
        "male": [35, 45, 55, 65],
        "female": [25, 35, 45, 55],
    },
    "broad_jump": {
        "unit": "cm",
        "higher_is_better": True,
        "reference": "Eurofit Test Battery",
        "male": [160, 180, 200, 220],
        "female": [120, 140, 160, 180],
    },
    "sit_ups": {
        "unit": "reps",
        "higher_is_better": True,
        "reference": "Cooper Institute Norms",
        "male": [20, 30, 40, 50],
        "female": [15, 25, 35, 45],
    },
    "sit_and_reach": {
        "unit": "cm",
        "higher_is_better": True,
        "reference": "YMCA Fitness Norms",
        "male": [13.4, 13.9, 14.6, 16.1],
        "female": [14.8, 15.5, 16.2, 17.4],
    },
    "sprint": {
        "unit": "sec",
        "higher_is_better": False,
        "reference": "NSCA Sprint Standards",
        "male": [5.2, 4.9, 4.5, 4.1],
        "female": [6.0, 5.6, 5.1, 4.5],
    },
    "shuttle_run": {
        "unit": "sec",
        "higher_is_better": False,
        "reference": "Eurofit Agility Norms",
        "male": [16.0, 15.0, 14.0, 13.0],
        "female": [17.0, 16.0, 15.0, 14.0],
    },
    "medicine_ball": {
        "unit": "cm",
        "higher_is_better": True,
        "reference": "NSCA Explosive Power",
        "male": [200, 300, 400, 500],
        "female": [150, 200, 300, 400],
    },
    "endurance_run": {
        "unit": "crossings",
        "higher_is_better": True,
        "reference": "Eurofit PACER Norms",
        "male": [5, 10, 15, 20],
        "female": [5, 10, 15, 20],
    },
}
