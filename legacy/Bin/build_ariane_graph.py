import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")


class UMLGraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run(self, query, **params):
        with self.driver.session() as session:
            session.run(query, **params)

    def create_constraints(self):
        self.run("""
        CREATE CONSTRAINT classe_nom IF NOT EXISTS
        FOR (c:Classe)
        REQUIRE c.nom IS UNIQUE
        """)

        self.run("""
        CREATE CONSTRAINT gamme_nom IF NOT EXISTS
        FOR (g:Gamme)
        REQUIRE g.nom IS UNIQUE
        """)

    def merge_gamme(self, nom):
        self.run("""
        MERGE (:Gamme {nom: $nom})
        """, nom=nom)

    def merge_classe(self, nom, attributs=None):
        if attributs is None:
            attributs = []

        self.run("""
        MERGE (c:Classe {nom: $nom})
        """, nom=nom)

        for attr in attributs:
            self.add_attribut_to_classe(
                classe=nom,
                attribut=attr["nom"],
                type_attr=attr.get("type")
            )

    def merge_enum(self, nom, valeurs):
        self.run("""
                  MERGE (e:Enum {nom:$nom})
    """, nom=nom)
        for valeur in valeurs:
            self.run("""
        MERGE (e:Enum {nom:$enum})
        MERGE (v:ValeurEnum {
            nom:$valeur,
            key:$key
        })
        MERGE (e)-[:A_VALEUR_ENUM]->(v)
        """,
        enum=nom,
        valeur=valeur,
        key=f"{nom}.{valeur}")
    
    def link_attribut_to_enum(self, classe, attribut, enum):
        key = f"{classe}.{attribut}"
        self.run("""
    MATCH (a:Attribut {key:$key})
    MERGE (e:Enum {nom:$enum})
    MERGE (a)-[:EST_DE_TYPE]->(e)
    """,
    key=key,
    enum=enum)

    def add_attribut_to_classe(self, classe, attribut, type_attr=None):
        key = f"{classe}.{attribut}"

        self.run("""
        MERGE (c:Classe {nom: $classe})
        MERGE (a:Attribut {key: $key})
        SET a.nom = $attribut
        MERGE (c)-[:A_ATTRIBUT]->(a)
        """, classe=classe, attribut=attribut, key=key)

        if type_attr:
            self.run("""
            MERGE (a:Attribut {key: $key})
            MERGE (t:Type {nom: $type_attr})
            MERGE (a)-[:EST_DE_TYPE]->(t)
            """, key=key, type_attr=type_attr)

    def add_relation(self, source, relation, target, nom_relation=None):
        allowed = {
            "HERITE_DE",
            "ASSOCIE_A",
            "COMPOSE_DE",
            "AGREGE",
            "REFERENCE",
            "DECRIT",
            "TYPE_PAR",
            "A_VALEUR"
        }

        if relation not in allowed:
            raise ValueError(f"Relation non autorisée : {relation}")

        query = f"""
        MERGE (s:Classe {{nom: $source}})
        MERGE (t:Classe {{nom: $target}})
        MERGE (s)-[r:{relation}]->(t)
        SET r.nom_relation = $nom_relation
        """

        self.run(query, source=source, target=target, nom_relation=nom_relation)

    def link_gamme_to_classe(self, gamme, classe):
        self.run("""
        MERGE (g:Gamme {nom: $gamme})
        MERGE (c:Classe {nom: $classe})
        MERGE (g)-[:DECRIT]->(c)
        """, gamme=gamme, classe=classe)


if __name__ == "__main__":
    builder = UMLGraphBuilder(URI, USER, PASSWORD)
    builder.create_constraints()


    #Gamme Habillage 

    gamme = "Gamme Habillage"
    builder.merge_gamme(gamme)

    builder.merge_classe("RessourceAbstraite")
    builder.merge_classe("RessourceAbstraiteNommee")

    builder.merge_classe("LocalisationSR")

    builder.merge_classe("HabillageOriente", [
        {"nom": "oriente", "type": "Boolean"},
        {"nom": "sens", "type": "EnumSensHabillage"}
    ])

    builder.merge_classe("HabillageValeur", [
        {"nom": "indCarto", "type": "Boolean"},
        {"nom": "libelle", "type": "String"},
        {"nom": "libelle_2", "type": "String"}
    ])

    builder.merge_classe("HabillageParcours")

    builder.merge_classe("HabillageRegle", [
        {"nom": "libelle", "type": "String"}
    ])

    builder.merge_classe("HabillageEntreprise")
    builder.merge_classe("HabillageRegionSNCF")
    builder.merge_classe("HabillageStructureAdministrative")

    builder.merge_classe("HabillageLocalDeVoie", [
        {"nom": "nomLocal", "type": "String"},
        {"nom": "nomThor", "type": "String"}
    ])

    builder.merge_classe("HabillageCourantMaxCatenaire", [
        {"nom": "courantMax", "type": "Integer"}
    ])

    builder.merge_classe("HabillageTension", [
        {"nom": "tension", "type": "String"}
    ])

    builder.merge_classe("VitesseParCodeComposition", [
        {"nom": "libelle", "type": "String"}
    ])

    builder.merge_classe("LocalisationPk", [
        {"nom": "indicCalcule", "type": "Boolean"},
        {"nom": "indicFiable", "type": "Boolean"},
        {"nom": "indicPkFictif", "type": "Boolean"},
        {"nom": "nomVoie", "type": "String"},
        {"nom": "origineLocalisation", "type": "EnumOrigineLocalisation"},
        {"nom": "positionLocalisation", "type": "EnumPositionLocalisation"},
        {"nom": "sensLecture", "type": "EnumSensLecture"}
    ])

    builder.merge_classe("SystemeReperage")
    builder.merge_classe("SystemeReperageVoie")

    builder.merge_classe("SystemeReperageLigne", [
        {"nom": "rang", "type": "Integer"}
    ])

    builder.merge_classe("SystemeReperagePk")
    builder.merge_classe("ElementTopologiqueOriente")

    builder.merge_classe("AssociationHabillage", [
        {"nom": "pkDebut", "type": "PK"},
        {"nom": "pkFin", "type": "PK"}
    ])

    builder.merge_classe("TypeHabillage", [
        {"nom": "code", "type": "String"},
        {"nom": "libelle", "type": "String"}
    ])

    builder.merge_classe("TypeHabillageOriente", [
        {"nom": "code", "type": "String"}
    ])

    builder.merge_classe("HabillageTypeValeur", [
        {"nom": "code", "type": "String"},
        {"nom": "libelle", "type": "String"}
    ])

    builder.merge_classe("TypeTension", [
        {"nom": "code", "type": "String"}
    ])

    builder.merge_classe("RessourceParcoursTopologique")

    builder.merge_classe("Entreprise", [
        {"nom": "code", "type": "String"},
        {"nom": "codeUIC", "type": "String"},
        {"nom": "ferroviale", "type": "Boolean"},
        {"nom": "sigle", "type": "String"}
    ])

    builder.merge_classe("RegionSNCF", [
        {"nom": "code", "type": "String"},
        {"nom": "mnemo", "type": "String"},
        {"nom": "parisienne", "type": "Boolean"}
    ])

    builder.merge_classe("StructureGeographique")

    for classe in [
        "HabillageOriente",
        "HabillageValeur",
        "HabillageParcours",
        "HabillageRegle",
        "HabillageEntreprise",
        "HabillageRegionSNCF",
        "HabillageStructureAdministrative",
        "HabillageLocalDeVoie",
        "HabillageCourantMaxCatenaire",
        "HabillageTension",
        "LocalisationPk",
        "SystemeReperageVoie",
        "TypeHabillage",
        "HabillageTypeValeur"
    ]:
        builder.link_gamme_to_classe(gamme, classe)

    # Héritage
    builder.add_relation("HabillageOriente", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("HabillageValeur", "HERITE_DE", "HabillageOriente")
    builder.add_relation("HabillageParcours", "HERITE_DE", "HabillageOriente")
    builder.add_relation("HabillageRegle", "HERITE_DE", "HabillageValeur")
    builder.add_relation("HabillageEntreprise", "HERITE_DE", "HabillageValeur")
    builder.add_relation("HabillageRegionSNCF", "HERITE_DE", "HabillageValeur")
    builder.add_relation("HabillageStructureAdministrative", "HERITE_DE", "HabillageValeur")
    builder.add_relation("HabillageLocalDeVoie", "HERITE_DE", "HabillageOriente")
    builder.add_relation("HabillageCourantMaxCatenaire", "HERITE_DE", "HabillageOriente")
    builder.add_relation("HabillageTension", "HERITE_DE", "HabillageOriente")
    builder.add_relation("VitesseParCodeComposition", "HERITE_DE", "HabillageOriente")
    builder.add_relation("LocalisationPk", "HERITE_DE", "LocalisationSR")
    builder.add_relation("SystemeReperageVoie", "HERITE_DE", "SystemeReperage")
    builder.add_relation("SystemeReperageLigne", "HERITE_DE", "SystemeReperage")

    # Associations / compositions
    builder.add_relation("HabillageOriente", "COMPOSE_DE", "LocalisationPk", "localisationsPk")
    builder.add_relation("LocalisationPk", "REFERENCE", "SystemeReperagePk", "systemeReperagePk")
    builder.add_relation("SystemeReperagePk", "REFERENCE", "SystemeReperageVoie", "systemeReperageVoie")
    builder.add_relation("LocalisationPk", "REFERENCE", "ElementTopologiqueOriente", "elementTopologique")

    builder.add_relation("HabillageOriente", "TYPE_PAR", "TypeHabillage", "typeHabillage")
    builder.add_relation("HabillageValeur", "A_VALEUR", "HabillageTypeValeur", "valeur")
    builder.add_relation("HabillageTension", "TYPE_PAR", "TypeTension", "typeTension")

    builder.add_relation("HabillageParcours", "ASSOCIE_A", "RessourceParcoursTopologique", "parcoursInfrastructure")
    builder.add_relation("HabillageEntreprise", "ASSOCIE_A", "Entreprise", "entrepriseInterconnectee")
    builder.add_relation("HabillageRegionSNCF", "ASSOCIE_A", "RegionSNCF", "regionInterconnectee")
    builder.add_relation("HabillageStructureAdministrative", "ASSOCIE_A", "StructureGeographique", "structureInterconnectee")


    #Gamme Fabrication Localisation et Implantation

    builder.merge_classe("LocalisationGeodesique", [{"nom": "coordoneeX", "type": "double"},{"nom": "coordoneeY", "type": "double"}, {"nom": "coordoneeZ", "type": "double"}])
    builder.merge_classe("LocalisationGare")
    builder.merge_classe("Localisation")
    builder.merge_classe("TypeImplantation", [{"nom": "code", "type": "String"}, {"nom": "mnemo", "type": "String"}])
    builder.merge_classe("LocalisationQuai", [{"nom": "lgQuai", "type": "String"}, {"nom": "lgUtile", "type": "String"},{"nom": "nomLocalVoie", "type": "String"}])
    builder.merge_classe("LocalisationOuvrageTerre", [{"nom" : "position", "type": "enumPositionOT"}])
    builder.merge_classe("LocalisationPkNiveau", [{"nom" : "indicateurPosition", "type": "String"}])
    builder.merge_classe("LocalisationPkTunnel")
    builder.merge_classe([])


    builder.close()
    print("Graphe UML Habillage avec attributs en nœuds créé.")
