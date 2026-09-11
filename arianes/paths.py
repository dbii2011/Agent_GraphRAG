"""Chemins partagés, indépendants du dossier depuis lequel une commande est lancée."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "project_data"
UML_DATA_DIR = DATA_ROOT / "uml"
PROCEDURES_DIR = DATA_ROOT / "procedures"
METIER_DATA_DIR = DATA_ROOT / "metier"
XMI_DATA_DIR = DATA_ROOT / "xmi"
TESTS_DIR = PROJECT_ROOT / "tests"
