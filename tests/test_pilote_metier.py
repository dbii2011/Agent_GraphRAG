import json
from pathlib import Path
from unittest.mock import MagicMock

from arianes.paths import METIER_DATA_DIR, PROCEDURES_DIR
from arianes.retrieval import GraphRAGRetriever
from arianes.pipelines.recontrole_metier import lire_passage
from arianes.pipelines.validation_metier import normaliser, verifier_import


def test_selection_pilote_preuves_et_conditions():
    root = Path(__file__).resolve().parents[1]
    selection = json.loads((METIER_DATA_DIR / 'pilote_poste_selection.json').read_text(encoding='utf-8'))
    verifier_import(selection)
    assert len(selection['concepts']) == 7
    assert len(selection['relations']) == 6
    for r in selection['relations']:
        assert normaliser(r['preuve']['citation']) in normaliser(lire_passage(r['preuve'], PROCEDURES_DIR))
        if r['type'] == 'LOCALISE_SUR':
            assert 'voie principale' in r['condition']
    assert 'SAF' not in [c['nom'] for c in selection['concepts']]


def test_preuves_metier_sans_embeddings():
    driver = MagicMock()
    record = MagicMock()
    record.data.return_value = {'chunk_id': 'post_0', 'texte': 'Une preuve.', 'position': 0,
                                'titre': 'Post.txt', 'document': 'Post.txt'}
    driver.session.return_value.__enter__.return_value.run.return_value = [record]
    r = GraphRAGRetriever(driver, None)
    resultat = r._chercher_preuves_metier({'relations': [{'chunk_ids': ['post_0', 'post_0']}]})
    assert resultat[0]['citation'] == 'Post.txt — passage 1'
    assert resultat[0]['origine_retrieval'] == 'preuve_graphe_metier'
    args = driver.session.return_value.__enter__.return_value.run.call_args.kwargs
    assert args['ids'] == ['post_0']


def test_structure_inclut_preuves_metier_sans_recherche_vectorielle():
    r = GraphRAGRetriever(None, None)
    r.resoudre_classes = lambda _: []
    r._construire_sous_graphe = lambda _: {'classes': []}
    r._construire_graphe_metier = lambda *_: {'relations': []}
    r._chercher_preuves_metier = lambda _: [{'chunk_id': 'post_0', 'citation': 'Post.txt — passage 1'}]
    r._chercher_chunks = MagicMock(side_effect=AssertionError('Aucun embedding attendu en mode structure'))
    resultat = r.retrieve('Quels attributs du poste ?')
    assert resultat['mode'] == 'STRUCTURE'
    assert resultat['citations'] == ['Post.txt — passage 1']
    r._chercher_chunks.assert_not_called()
