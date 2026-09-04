from selectionner_graphe_metier_prudent import est_acceptable, selectionner


def test_accepte_uniquement_l_avertissement_de_categorie():
    assert est_acceptable({"statut": "A_REVOIR", "avertissements": []})
    assert est_acceptable({
        "statut": "A_REVOIR",
        "avertissements": ["catégorie source ou cible à préciser"],
    })
    assert not est_acceptable({
        "statut": "A_REVOIR",
        "avertissements": ["prédicat non confirmé textuellement"],
    })
    assert not est_acceptable({"statut": "REJETE", "avertissements": []})


def test_selection_ne_garde_que_les_concepts_utilises():
    definition = {
        "domaine": "test",
        "concepts": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "relations": [
            {"source": "a", "type": "EST_UN", "cible": "b", "statut": "A_REVOIR"},
            {"source": "b", "type": "UTILISE", "cible": "c", "statut": "REJETE"},
        ],
    }
    resultat = selectionner(definition)
    assert [c["id"] for c in resultat["concepts"]] == ["a", "b"]
    assert len(resultat["relations"]) == 1
    assert resultat["relations"][0]["statut"] == "VALIDE"
    assert resultat["relations_exclues"] == 1
