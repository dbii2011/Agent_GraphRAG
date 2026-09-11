from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

from arianes.graph.metier_builder import importer
from arianes.paths import METIER_DATA_DIR
from arianes.pipelines.extraction_metier import consolider, extraire_json_message
from arianes.pipelines.recontrole_metier import lire_passage, recontroler
from arianes.pipelines.validation_metier import controler_relation, corriger_relation, verifier_import


def relation(s="signal", t="EST_COMMANDE_PAR", c="poste", citation="Le signal est commandé par le poste.", doc="Post.txt"):
    return {"source": s, "type": t, "cible": c, "statut": "A_REVOIR",
            "preuve": {"document": doc, "lignes": "1-1", "citation": citation}}


def concepts(*noms):
    return {n: {"id": n, "nom": n.replace("_", " "), "statut": "A_REVOIR"} for n in noms}


def test_corrige_rk_sans_modifier_original():
    r = relation("point_kilometrique", "EST_UN", "repere_kilometrique", "Le RK est un PK particulier dont la distance est égale à zéro.", "Ligne.txt")
    original = deepcopy(r)
    corrige = corriger_relation(r)
    assert r == original
    assert corrige["source"] == "repere_kilometrique"
    assert corrige["corrections"]
    assert corriger_relation(corrige) == corrige


def test_aucune_inversion_sans_preuve_attendue():
    r = relation("point_kilometrique", "EST_UN", "repere_kilometrique")
    assert corriger_relation(r) == r


def test_passif_ne_modifie_pas_une_autre_relation():
    r = relation("signal", "LOCALISE_SUR", "poste")
    assert controler_relation(r, concepts("signal", "poste"))["type"] == "LOCALISE_SUR"


def test_passif_controller_en_source_est_inverse():
    r = relation("poste", "COMMANDE", "signal")
    controle = controler_relation(r, concepts("signal", "poste"))
    assert (controle["source"], controle["type"], controle["cible"]) == ("signal", "EST_COMMANDE_PAR", "poste")


def test_document_ne_commande_pas_un_poste():
    r = relation("poste", "EST_COMMANDE_PAR", "plan_technique", "Le poste est commandé par le plan technique.")
    assert controler_relation(r, concepts("poste", "plan_technique"))["statut"] == "REJETE"


def test_incertitude_devient_probable():
    r = relation("a", "EST_UN", "b", "Une description ambiguë dans la fiche.")
    controle = controler_relation(r, concepts("a", "b"), r["preuve"]["citation"])
    assert controle["statut"] == "PROBABLE"
    assert "prédicat non confirmé textuellement" in controle["avertissements"]


def test_citation_negation_est_signalee():
    r = relation(citation="Le signal ne doit pas être commandé par le poste.")
    controle = controler_relation(r, concepts("signal", "poste"), r["preuve"]["citation"])
    assert any("négation" in a for a in controle["avertissements"])


def test_fusion_ne_cree_pas_auto_relation():
    entree = {"domaine": "Test", "concepts": [{"id": "a", "nom": "Ligne"}, {"id": "b", "nom": "Ligne"}],
              "relations": [relation("a", "EST_UN", "b")]}
    sortie = consolider([entree])
    assert not sortie["relations"]
    assert sortie["relations_rejetees"][0]["statut"] == "REJETE"


def test_import_direct_refuse_avant_toute_ecriture():
    driver = Mock()
    with pytest.raises(ValueError, match="ni VALIDE ni PROBABLE"):
        importer(driver, {"concepts": list(concepts("signal", "poste").values()), "relations": [relation()]})
    driver.session.assert_not_called()


def test_import_refuse_self_meme_marquee_valide():
    definition = {"concepts": [{"id": "a", "statut": "VALIDE"}],
                  "relations": [{**relation("a", "EST_UN", "a"), "statut": "VALIDE"}]}
    with pytest.raises(ValueError, match="extrémités"):
        verifier_import(definition)


def test_recontrole_citation_hors_lignes(tmp_path):
    (tmp_path / "Post.txt").write_text("Autre phrase.\nLe signal est commandé par le poste.\n", encoding="utf-8")
    entree = {"concepts": list(concepts("signal", "poste").values()), "relations": [relation()]}
    copie = deepcopy(entree)
    sortie = recontroler(entree, tmp_path)
    assert entree == copie
    assert not sortie["relations"]
    assert "citation absente du passage" in sortie["relations_rejetees"][0]["motifs_rejet"]


def test_chemin_document_hors_corpus_est_refuse(tmp_path):
    with pytest.raises(ValueError, match="hors du corpus"):
        lire_passage({"document": "../secret.txt", "lignes": "1-1"}, tmp_path)


def test_json_controle_litteral():
    assert extraire_json_message('{"citation": "ligne 1\nligne 2"}')["citation"] == "ligne 1\nligne 2"


def test_import_preserve_plusieurs_preuves_du_meme_triplet():
    cs = list(concepts("signal", "poste").values())
    for c in cs:
        c.update(statut="VALIDE", aliases=[], description="", documents=[])
    r1 = {**relation(), "statut": "VALIDE"}
    r2 = deepcopy(r1)
    r2["preuve"]["document"] = "ZoneDeDetection.txt"
    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.run.return_value.single.return_value = {"concepts": 2, "relations": 2}
    importer(driver, {"domaine": "Test", "concepts": cs, "relations": [r1, r2]})
    appels = [c for c in session.run.call_args_list if "MERGE (a)-[r:RELATION_METIER" in c.args[0]]
    assert len(appels) == 2
    assert all("source_document: $source_document, preuve: $citation, lignes: $lignes}" in c.args[0] for c in appels)
    assert appels[0].kwargs["source_document"] != appels[1].kwargs["source_document"]


def test_consolidation_conserve_deux_preuves():
    r1 = relation()
    r2 = deepcopy(r1)
    r2["preuve"]["document"] = "ZoneDeDetection.txt"
    g = consolider([{"domaine": "Test", "concepts": list(concepts("signal", "poste").values()),
                     "relations": [r1, r2, deepcopy(r1)]}])
    assert len(g["relations"]) == 2


def test_copie_corrigee_structure_et_statuts():
    import json
    racine = Path(__file__).resolve().parents[1]
    sortie = METIER_DATA_DIR / "corrections_v3"
    if not sortie.exists():
        pytest.skip("Audit local non livré avec ce checkout")
    rapport = json.loads((sortie / "rapport_controle.json").read_text(encoding="utf-8"))
    g = json.loads((sortie / "proposition_globale.json").read_text(encoding="utf-8"))
    assert len(g["relations"]) == rapport["relations_conservees_a_revoir"]
    assert all(
        r["source"] != r["cible"] and r["statut"] in {"VALIDE", "PROBABLE"}
        for r in g["relations"]
    )


@pytest.mark.parametrize("source,predicat,cible,citation,doc,attendu", [
    ("quai", "COMPOSE_DE", "hauteur_du_quai", "La hauteur du quai", "Quai.txt", "A_POUR_CARACTERISTIQUE"),
    ("quai", "LOCALISE_SUR", "plan_technique", "Forme de remontée : Plan technique", "Quai.txt", "DECRIT_PAR"),
    ("date_de_debut_de_fermeture", "LOCALISE_SUR", "fermeture_temporaire", "Renseigner la date de début de la fermeture", "Ligne.txt", "DEBUTE_A"),
])
def test_corrections_semantiques(source, predicat, cible, citation, doc, attendu):
    assert corriger_relation(relation(source, predicat, cible, citation, doc))["type"] == attendu
