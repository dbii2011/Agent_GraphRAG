"""Prépare les preuves du pilote, vérifie ses rattachements puis importe sur demande."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from arianes.graph.metier_builder import importer
from arianes.paths import METIER_DATA_DIR, PROCEDURES_DIR, PROJECT_ROOT
from arianes.pipelines.recontrole_metier import lire_passage
from arianes.pipelines.validation_metier import normaliser, verifier_import

RACINE = PROJECT_ROOT


def preparer(driver, definition, docs):
    resultat = deepcopy(definition)
    verifier_import(resultat)
    with driver.session() as session:
        for concept in resultat['concepts']:
            for nom in concept.get('classes_arianes', []):
                n = session.run('MATCH (c:Classe {nom:$nom}) RETURN count(c) AS n', nom=nom).single()['n']
                if n != 1:
                    raise ValueError(f'Classe absente ou ambiguë : {nom} ({n})')
            for doc in concept.get('documents', []):
                n = session.run(
                    'MATCH (d:Document) WHERE toLower(d.id) ENDS WITH toLower($nom) '
                    'OR toLower(d.titre) ENDS WITH toLower($nom) RETURN count(d) AS n', nom=doc
                ).single()['n']
                if n != 1:
                    raise ValueError(f'Document absent ou ambigu : {doc} ({n})')
        for relation in resultat['relations']:
            preuve = relation['preuve']
            citation = normaliser(preuve['citation'])
            if f' {citation} ' not in f' {normaliser(lire_passage(preuve, docs))} ':
                raise ValueError(f'Citation absente des lignes : {preuve}')
            chunks = [dict(r) for r in session.run(
                'MATCH (c:Chunk)-[:APPARTIENT_A]->(d:Document) '
                'WHERE toLower(d.id) ENDS WITH toLower($nom) OR toLower(d.titre) ENDS WITH toLower($nom) '
                'RETURN c.id AS id,c.texte AS texte ORDER BY c.position', nom=preuve['document']
            )]
            preuve['chunk_ids'] = [c['id'] for c in chunks if f' {citation} ' in f" {normaliser(c['texte'])} "]
            if not preuve['chunk_ids']:
                raise ValueError(f'Aucun chunk ne contient la citation : {preuve}')
        # Ne pas écraser des concepts métier existants de contenu différent.
        for c in resultat['concepts']:
            existant = session.run('MATCH (c:ConceptMetier {id:$id}) RETURN c.nom AS nom,c.domaine AS domaine', id=c['id']).single()
            if existant and (existant['nom'] != c['nom'] or existant['domaine'] != resultat['domaine']):
                raise ValueError(f"Concept métier existant hors pilote : {c['id']}")
    return resultat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--importer', action='store_true', help='Autoriser les écritures métier après tous les contrôles')
    args = parser.parse_args()
    load_dotenv(RACINE / '.env')
    definition = json.loads((METIER_DATA_DIR / 'pilote_poste_selection.json').read_text(encoding='utf-8'))
    with GraphDatabase.driver(os.getenv('NEO4J_URI','bolt://127.0.0.1:7687'), auth=(os.getenv('NEO4J_USER','neo4j'),os.getenv('NEO4J_PASSWORD'))) as driver:
        pilote = preparer(driver, definition, PROCEDURES_DIR)
        if args.importer:
            resultat = importer(driver, pilote)
            print(json.dumps(resultat, ensure_ascii=True))
        else:
            print('Précontrôle OK, aucune écriture dans Neo4j.')
        print(json.dumps({'concepts':len(pilote['concepts']), 'relations':len(pilote['relations']),
                          'chunks':sorted({i for r in pilote['relations'] for i in r['preuve']['chunk_ids']})},ensure_ascii=True))


if __name__ == '__main__':
    main()
