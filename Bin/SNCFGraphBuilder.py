import json
from neo4j import GraphDatabase


URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "password"


class SNCFGraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run(self, query, **params):
        with self.driver.session() as session:
            session.run(query, **params)

    def create_constraints(self):
        constraints = [
            "CREATE CONSTRAINT ligne_code IF NOT EXISTS FOR (l:Ligne) REQUIRE l.code_ligne IS UNIQUE",
            "CREATE CONSTRAINT gare_id IF NOT EXISTS FOR (g:Gare) REQUIRE g.idgaia IS UNIQUE",
            "CREATE CONSTRAINT quai_id IF NOT EXISTS FOR (q:Quai) REQUIRE q.idgaia IS UNIQUE",
            "CREATE CONSTRAINT chantier_id IF NOT EXISTS FOR (c:Chantier) REQUIRE c.idgaia IS UNIQUE",
            "CREATE CONSTRAINT triage_id IF NOT EXISTS FOR (t:Triage) REQUIRE t.idgaia IS UNIQUE",
            "CREATE CONSTRAINT pont_id IF NOT EXISTS FOR (p:Pont) REQUIRE p.idgaia IS UNIQUE",
            "CREATE CONSTRAINT circuit_id IF NOT EXISTS FOR (c:CircuitDeVoie) REQUIRE c.idgaia IS UNIQUE",
            "CREATE CONSTRAINT voie_code IF NOT EXISTS FOR (v:Voie) REQUIRE v.code_voie IS UNIQUE",
        ]

        for c in constraints:
            self.run(c)

    def merge_ligne(self, code_ligne, lib_ligne=None):
        if not code_ligne:
            return

        self.run("""
        MERGE (l:Ligne:RessourceAbstraite {code_ligne: $code_ligne})
        SET l.libelle = coalesce($lib_ligne, l.libelle),
            l.type_ariane = "RessourceFonctionnelle"
        """, code_ligne=code_ligne, lib_ligne=lib_ligne)

    def merge_simple_object(self, label, obj, dataset_name):
        idgaia = obj.get("idgaia")
        if not idgaia:
            return

        code_ligne = obj.get("code_ligne")
        libelle = obj.get("libelle") or obj.get("nom_ifx")

        self.merge_ligne(code_ligne, obj.get("lib_ligne"))

        query = f"""
        MERGE (n:{label}:RessourceAbstraite:InstallationFixe {{idgaia: $idgaia}})
        SET n.libelle = $libelle,
            n.idreseau = $idreseau,
            n.code_ligne = $code_ligne,
            n.rg_troncon = $rg_troncon,
            n.pk = $pk,
            n.pkd = $pkd,
            n.pkf = $pkf,
            n.source_dataset = $dataset_name,
            n.type_ariane = "InstallationFixe",
            n.longitude = $longitude,
            n.latitude = $latitude

        WITH n
        MATCH (l:Ligne {{code_ligne: $code_ligne}})
        MERGE (n)-[r:EST_SUR_LIGNE]->(l)
        SET r.pk = $pk,
    r.pkd = $pkd,
    r.pkf = $pkf,
    r.rg_troncon = $rg_troncon
        """

        geo = obj.get("geo_point_2d") or obj.get("c_geo") or {}

        self.run(
            query,
            idgaia=idgaia,
            libelle=libelle,
            idreseau=obj.get("idreseau") or obj.get("id_if"),
            code_ligne=code_ligne,
            rg_troncon=obj.get("rg_troncon"),
            pk=obj.get("pk"),
            pkd=obj.get("pkd"),
            pkf=obj.get("pkf"),
            dataset_name=dataset_name,
            longitude=geo.get("lon"),
            latitude=geo.get("lat"),
        )

    def merge_gare(self, obj):
        idgaia = obj.get("idgaia")
        if not idgaia:
            return

        code_ligne = obj.get("code_ligne")
        self.merge_ligne(code_ligne)

        self.run("""
        MERGE (g:Gare:RessourceAbstraite:InstallationFixe {idgaia: $idgaia})
        SET g.libelle = $libelle,
            g.code_uic = $code_uic,
            g.idreseau = $idreseau,
            g.code_ligne = $code_ligne,
            g.commune = $commune,
            g.departement = $departement,
            g.pk = $pk,
            g.voyageurs = $voyageurs,
            g.fret = $fret,
            g.type_ariane = "InstallationFixe",
            g.source_dataset = "gares",
            g.longitude = $longitude,
            g.latitude = $latitude

        WITH g
        MATCH (l:Ligne {code_ligne: $code_ligne})
        MERGE (g)-[r:Ec'estST_SUR_LIGNE]->(l)
        SET r.pk = $pk,
        r.rg_troncon = $rg_troncon
        """,
        idgaia=idgaia,
        libelle=obj.get("libelle"),
        code_uic=obj.get("code_uic"),
        idreseau=obj.get("idreseau"),
        code_ligne=code_ligne,
        commune=obj.get("commune"),
        departement=obj.get("departemen"),
        pk=obj.get("pk"),
        voyageurs=obj.get("voyageurs"),
        fret=obj.get("fret"),
        rg_troncon=obj.get("rg_troncon"),
        longitude=(obj.get("geo_point_2d") or {}).get("lon"),
        latitude=(obj.get("geo_point_2d") or {}).get("lat"),
        )

    def merge_quai(self, obj):
        self.merge_simple_object("Quai", obj, "quais")

        lib_gare = obj.get("lib_gare")
        idgaia = obj.get("idgaia")

        if lib_gare and idgaia:
            self.run("""
            MATCH (q:Quai {idgaia: $idgaia})
            MATCH (g:Gare)
            WHERE toLower(g.libelle) = toLower($lib_gare)
            MERGE (q)-[:APPARTIENT_A_GARE]->(g)
            """, idgaia=idgaia, lib_gare=lib_gare)

    def merge_chantier(self, obj):
        self.merge_simple_object("Chantier", obj, "chantiers")

        gare = obj.get("gare")
        idgaia = obj.get("idgaia")

        if gare and idgaia:
            self.run("""
            MATCH (c:Chantier {idgaia: $idgaia})
            MATCH (g:Gare)
            WHERE toLower(g.libelle) = toLower($gare)
            MERGE (c)-[:APPARTIENT_A_GARE]->(g)
            """, idgaia=idgaia, gare=gare)

    def merge_circuit(self, obj):
        self.merge_simple_object("CircuitDeVoie", obj, "circuit")

        code_voie = obj.get("code_voie")
        code_ligne = obj.get("code_ligne")
        idgaia = obj.get("idgaia")

        if code_voie:
            self.merge_ligne(code_ligne)

            self.run("""
            MERGE (v:Voie:RessourceAbstraite {code_voie: $code_voie})
            SET v.nom_voie = $nom_voie,
                v.code_ligne = $code_ligne,
                v.type_ariane = "RessourceFonctionnelle"

            WITH v
            MATCH (l:Ligne {code_ligne: $code_ligne})
            MERGE (v)-[:APPARTIENT_A_LIGNE]->(l)

            WITH v
            MATCH (c:CircuitDeVoie {idgaia: $idgaia})
            MERGE (c)-[:EST_SUR_VOIE]->(v)
            """,
            code_voie=code_voie,
            nom_voie=obj.get("nom_voie"),
            code_ligne=code_ligne,
            idgaia=idgaia,
            )

    def build_from_file(self, filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.create_constraints()
        for obj in data.get("gares", {}).get("results", []):
            self.merge_gare(obj)

        for obj in data.get("quais", {}).get("results", []):
            self.merge_quai(obj)

        for obj in data.get("chantiers", {}).get("results", []):
            self.merge_chantier(obj)

        simple_mappings = {
            "ponts": "Pont",
            "triages": "Triage",
            "passages souterrains": "PassageSouterrain",
            "liste des passerelles": "Passerelle",
            "liste des passages à niveau": "PassageANiveau",
        }

        for dataset_name, label in simple_mappings.items():
            for obj in data.get(dataset_name, {}).get("results", []):
                self.merge_simple_object(label, obj, dataset_name)

        for obj in data.get("circuit", {}).get("results", []):
            self.merge_circuit(obj)


if __name__ == "__main__":
    builder = SNCFGraphBuilder(URI, USER, PASSWORD)
    builder.build_from_file("data.json")
    builder.close()

    print("Graphe minimal créé.")