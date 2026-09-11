from arianes.pipelines.selection_prudente import est_acceptable, selectionner


def test_accepte_valide_et_probable_sans_motif_bloquant():
    assert est_acceptable({"statut": "VALIDE", "avertissements": []})
    assert est_acceptable({
        "statut": "PROBABLE",
        "avertissements": ["catégorie source ou cible à préciser"],
    })
    assert est_acceptable({"statut": "PROBABLE", "avertissements": ["prédicat non confirmé textuellement"]})
    assert not est_acceptable({"statut": "REJETE", "avertissements": []})
    assert not est_acceptable({"statut": "PROBABLE", "motifs_rejet": ["preuve absente"]})


def test_selection_ne_garde_que_les_concepts_utilises():
    definition = {
        "domaine": "test",
        "concepts": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "relations": [
            {"source": "a", "type": "EST_UN", "cible": "b", "statut": "PROBABLE"},
            {"source": "b", "type": "UTILISE", "cible": "c", "statut": "REJETE"},
        ],
    }
    resultat = selectionner(definition)
    assert [c["id"] for c in resultat["concepts"]] == ["a", "b"]
    assert len(resultat["relations"]) == 1
    assert resultat["relations"][0]["statut"] == "PROBABLE"
    assert resultat["relations_exclues"] == 1
