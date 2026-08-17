"""
ARIANE Graph Builder — Neo4j  v2
=================================
Squelette UML complet pour agent GraphRAG.

Sources intégrées :
  G1  — Ariane Cœur V0.1
  G2  — RessourceInstallationFixe V1
  G3  — Topologie V0.1
  G4  — Système de repérage V1
  G5  — Localisation et Implantation V0
  G6  — SAF V1
  G7  — Représentation géométrique d'un élément topologique V0.1
  G8  — Repère de calibrage V0.1
  G9  — Passage à Niveau V9
  G10 — Point d'information ETCS V9
  G11 — Transit et Groupement de Zone V5
  G12 — Point d'information KVB V6
"""

from neo4j import GraphDatabase

URI      = "bolt://127.0.0.1:7687"
USER     = "neo4j"
PASSWORD = "db200402"

RELATIONS_AUTORISEES = {
    "HERITE_DE",
    "COMPOSE_DE",
    "AGREGE",
    "ASSOCIE_A",
    "TYPE_PAR",
    "DECRIT",
    # Traçabilité
    "A_POUR_PROVENANCE",
    "A_POUR_CHECKSUM",
    "A_POUR_REVISION",
    # Caractéristiques & implantation
    "A_POUR_CARACTERISTIQUE",
    "A_POUR_IMPLANTATION",
    "IMPLANTATION_CONTIENT",
    # Physique
    "A_POUR_TYPE_ASSOCIATION",
    "PORTE_SUR_RESSOURCE_PHYSIQUE",
    # Structurel
    "PORTE_SUR_RESSOURCE_STRUCTURELLE",
    "APPARTIENT_A_LIGNE",
    # IFX
    "A_POUR_ETAT",
}


class ArianeGraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def _run(self, query, **params):
        with self.driver.session() as session:
            session.run(query, **params)

    # ------------------------------------------------------------------
    # Contraintes
    # ------------------------------------------------------------------
    def create_constraints(self):
        for stmt in [
            "CREATE CONSTRAINT classe_nom  IF NOT EXISTS FOR (c:Classe)   REQUIRE c.nom IS UNIQUE",
            "CREATE CONSTRAINT gamme_nom   IF NOT EXISTS FOR (g:Gamme)    REQUIRE g.nom IS UNIQUE",
            "CREATE CONSTRAINT enum_nom    IF NOT EXISTS FOR (e:Enum)     REQUIRE e.nom IS UNIQUE",
            "CREATE CONSTRAINT type_nom    IF NOT EXISTS FOR (t:Type)     REQUIRE t.nom IS UNIQUE",
            "CREATE CONSTRAINT attr_key    IF NOT EXISTS FOR (a:Attribut) REQUIRE a.key IS UNIQUE",
        ]:
            self._run(stmt)

    # ------------------------------------------------------------------
    # Gamme
    # ------------------------------------------------------------------
    def merge_gamme(self, nom, version=None, date=None):
        self._run(
            "MERGE (g:Gamme {nom:$nom}) SET g.version=$version, g.date=$date",
            nom=nom, version=version, date=date,
        )

    def lier_gamme_classe(self, gamme, classe):
        self._run(
            "MERGE (g:Gamme{nom:$g}) MERGE (c:Classe{nom:$c}) MERGE (g)-[:DECRIT]->(c)",
            g=gamme, c=classe,
        )

    # ------------------------------------------------------------------
    # Classe
    # ------------------------------------------------------------------
    def merge_classe(self, nom, description=None, abstraite=False, attributs=None):
        self._run(
            "MERGE (c:Classe{nom:$nom}) SET c.description=$desc, c.abstraite=$abs",
            nom=nom, desc=description, abs=abstraite,
        )
        for a in (attributs or []):
            self._merge_attribut(classe=nom, **a)

    def _merge_attribut(self, classe, nom, type=None, description=None,
                        defaut=None, deprecated=False, obligatoire=None):
        key = f"{classe}.{nom}"
        self._run(
            """
            MERGE (c:Classe{nom:$classe})
            MERGE (a:Attribut{key:$key})
            SET a.nom=$nom, a.description=$desc, a.defaut=$defaut,
                a.deprecated=$dep, a.obligatoire=$obl
            MERGE (c)-[:A_ATTRIBUT]->(a)
            """,
            classe=classe, key=key, nom=nom, desc=description,
            defaut=defaut, dep=deprecated, obl=obligatoire,
        )
        if type:
            label = "Enum" if type.startswith("Enum") else "Type"
            self._run(
                f"MERGE (a:Attribut{{key:$key}}) MERGE (t:{label}{{nom:$t}}) MERGE (a)-[:EST_DE_TYPE]->(t)",
                key=key, t=type,
            )

    # ------------------------------------------------------------------
    # Enum
    # ------------------------------------------------------------------
    def merge_enum(self, nom, valeurs):
        self._run("MERGE (:Enum{nom:$nom})", nom=nom)
        for v in valeurs:
            self._run(
                "MERGE (e:Enum{nom:$e}) MERGE (val:ValeurEnum{key:$k}) SET val.nom=$v MERGE (e)-[:A_VALEUR]->(val)",
                e=nom, v=v, k=f"{nom}.{v}",
            )

    # ------------------------------------------------------------------
    # Relation UML
    # ------------------------------------------------------------------
    def add_relation(self, source, relation, target, role=None, cardinalite=None):
        if relation not in RELATIONS_AUTORISEES:
            raise ValueError(f"Relation non autorisée : '{relation}'")
        self._run(
            f"""
            MERGE (s:Classe{{nom:$s}}) MERGE (t:Classe{{nom:$t}})
            MERGE (s)-[r:{relation}]->(t)
            SET r.role=$role, r.cardinalite=$card
            """,
            s=source, t=target, role=role, card=cardinalite,
        )


# ======================================================================
def main():
    b = ArianeGraphBuilder(URI, USER, PASSWORD)
    b.create_constraints()

    # ==================================================================
    # G1 — Ariane Cœur V0.1
    # ==================================================================
    G1 = "Ariane Cœur"
    b.merge_gamme(G1, "V0.1", "2023-05-12")

    b.merge_classe("ObjetPersistant", abstraite=True,
        description="Racine de toutes les entités ARIANE. Fournit id, dateCreation et revision.",
        attributs=[
            {"nom": "id",           "type": "P-String",   "description": "UUID RFC4122 128 bits.", "obligatoire": True},
            {"nom": "dateCreation", "type": "P-Datetime",  "obligatoire": True},
            {"nom": "revision",     "type": "P-Long",
             "description": "Timestamp secondes depuis 01/01/1970 UTC, strictement croissant.", "obligatoire": True},
        ])

    b.merge_classe("ReferenceObjetRevision",
        description="Référence figée à une révision précise d'un objet persistant.",
        attributs=[{"nom": "revision", "type": "P-Long"}])

    b.merge_classe("RessourceAbstraite", abstraite=True,
        description="Étend ObjetPersistant avec DDA, DFA (à minuit) et idExterne.",
        attributs=[
            {"nom": "dateDebutActivite", "type": "P-Datetime",
             "description": "DDA — incluse dans l'intervalle, à minuit.", "obligatoire": True},
            {"nom": "dateFinActivite",   "type": "P-Datetime",
             "description": "DFA — exclue de l'intervalle, à minuit.", "obligatoire": True},
            {"nom": "idExterne", "type": "P-Long",
             "description": "Identifiant réseau pour communication SI."},
        ])

    b.merge_classe("RessourceAbstraiteNommee", abstraite=True,
        description="Ajoute une collection de libellés datés. Toujours libellé présent sur toute la durée de vie.")

    b.merge_classe("ElementADateAbstrait", abstraite=True,
        description="Élément portant DDA et DFA à minuit, DFA exclue.",
        attributs=[
            {"nom": "dateDebutActivite", "type": "P-Datetime", "obligatoire": True},
            {"nom": "dateFinActivite",   "type": "P-Datetime", "obligatoire": True},
        ])

    b.merge_classe("LibelleRessource",
        description="Libellé daté d'une ressource nommée. Plusieurs libellés peuvent se succéder.",
        attributs=[{"nom": "libelle", "type": "P-String", "obligatoire": True}])

    b.merge_classe("ImplantationAbstraite", abstraite=True,
        description="Implantation fonctionnelle ou physique d'une ressource. Peut être composite.")

    b.merge_classe("ProvenanceObjet",
        description="Trace l'origine d'un objet (entité, projet, service).",
        attributs=[
            {"nom": "codeEntite",    "type": "P-String"},
            {"nom": "libelleEntite", "type": "P-String"},
            {"nom": "codeProjet",    "type": "P-String"},
            {"nom": "codeService",   "type": "P-String"},
        ])
    b.merge_classe("TypeProvenance",     attributs=[{"nom": "provenance", "type": "P-String"}])
    b.merge_classe("Objectchecksum",
        description="Empreinte d'intégrité d'un objet persistant.",
        attributs=[{"nom": "checksum", "type": "P-String"}])

    b.merge_classe("CaracteristiqueElement", abstraite=True)
    b.merge_classe("CaracteristiqueSymbole")
    b.merge_classe("LigneProduit", attributs=[
        {"nom": "code"}, {"nom": "mnemo"}, {"nom": "contact"}, {"nom": "responsable"}])

    b.merge_classe("RessourcePhysique",       abstraite=True)
    b.merge_classe("RessourcePhysiqueUnitaire", attributs=[
        {"nom": "dateFabrication", "type": "P-Datetime"},
        {"nom": "identifiant",     "type": "P-String"}])
    b.merge_classe("RessourcePhysiqueMesurable", attributs=[
        {"nom": "dateDePoste", "type": "P-Datetime"}])
    b.merge_classe("TypeAssociationRessourcePhysique", attributs=[{"nom": "code", "type": "P-String"}])
    b.merge_classe("AssociationRessourcePhysique",     attributs=[{"nom": "dateAssociation", "type": "P-Datetime"}])

    b.merge_classe("RessourceStructurelle",           attributs=[{"nom": "mnemo", "type": "P-String"}])
    b.merge_classe("AssociationRessourceStructurelle", attributs=[
        {"nom": "dateAssociation", "type": "P-Datetime"},
        {"nom": "quantite",        "type": "P-Double"}])

    b.merge_classe("TypeEtat", attributs=[{"nom": "code", "type": "P-String"}, {"nom": "mnemo", "type": "P-String"}])

    b.merge_classe("RessourceInstallationFixe",
        description="Installation fixe ferroviaire (IFX). Toujours liée à un unique TypeInstallationFixe dans le temps.",
        attributs=[
            {"nom": "coordonneeX",    "type": "P-Integer", "defaut": "-10", "deprecated": True,
             "description": "Supprimé en V3. Défaut -10."},
            {"nom": "coordonneeY",    "type": "P-Integer", "defaut": "-10", "deprecated": True,
             "description": "Supprimé en V3. Défaut -10."},
            {"nom": "dateFinService", "type": "P-Datetime",
             "description": "DFS — valorisée automatiquement à la même date que la DFA sauf indication contraire."},
            {"nom": "libelleObstacle","type": "P-String",  "defaut": "NULL",
             "description": "NULL par défaut. Renseigné par le gérant pour les PN."},
            {"nom": "longueur",       "type": "P-Integer", "defaut": "NULL"},
        ])
    b.merge_classe("InstallationFixeVirtuelle",
        description="Sous-type virtuel de RessourceInstallationFixe (pas d'implantation physique).")

    # Relations G1
    for src, tgt in [
        ("RessourceAbstraite",        "ObjetPersistant"),
        ("RessourceAbstraiteNommee",  "RessourceAbstraite"),
        ("LibelleRessource",          "ElementADateAbstrait"),
        ("RessourcePhysique",         "RessourceAbstraiteNommee"),
        ("RessourcePhysiqueUnitaire", "RessourcePhysique"),
        ("RessourcePhysiqueMesurable","RessourcePhysique"),
        ("RessourceStructurelle",     "RessourceAbstraiteNommee"),
        ("RessourceInstallationFixe", "RessourceAbstraiteNommee"),
        ("InstallationFixeVirtuelle", "RessourceInstallationFixe"),
        ("CaracteristiqueSymbole",    "CaracteristiqueElement"),
        ("LigneProduit",              "CaracteristiqueElement"),
    ]:
        b.add_relation(src, "HERITE_DE", tgt)

    b.add_relation("RessourceAbstraiteNommee",        "COMPOSE_DE", "LibelleRessource",
                   role="libelles", cardinalite="1..*")
    b.add_relation("ObjetPersistant", "A_POUR_PROVENANCE", "ProvenanceObjet")
    b.add_relation("ProvenanceObjet", "TYPE_PAR",          "TypeProvenance")
    b.add_relation("ObjetPersistant", "A_POUR_CHECKSUM",   "Objectchecksum")
    b.add_relation("ObjetPersistant", "A_POUR_REVISION",   "ReferenceObjetRevision")
    b.add_relation("RessourceAbstraite", "A_POUR_CARACTERISTIQUE", "CaracteristiqueElement", role="caracteristiques")
    b.add_relation("RessourceAbstraite", "A_POUR_IMPLANTATION",    "ImplantationAbstraite",  role="implantationFonctionnelle")
    b.add_relation("ImplantationAbstraite", "IMPLANTATION_CONTIENT", "ImplantationAbstraite", role="implantations")
    b.add_relation("AssociationRessourcePhysique",    "A_POUR_TYPE_ASSOCIATION",      "TypeAssociationRessourcePhysique")
    b.add_relation("AssociationRessourcePhysique",    "PORTE_SUR_RESSOURCE_PHYSIQUE", "RessourcePhysique")
    b.add_relation("AssociationRessourceStructurelle","PORTE_SUR_RESSOURCE_STRUCTURELLE","RessourceStructurelle")
    b.add_relation("RessourceStructurelle",           "APPARTIENT_A_LIGNE",           "LigneProduit", role="ligneParente")
    b.add_relation("RessourceInstallationFixe",       "A_POUR_ETAT",                 "TypeEtat", role="typeEtat")

    for c in ["ObjetPersistant","ReferenceObjetRevision","RessourceAbstraite","RessourceAbstraiteNommee",
              "ElementADateAbstrait","LibelleRessource","ImplantationAbstraite","TypeEtat",
              "RessourceInstallationFixe","InstallationFixeVirtuelle","RessourcePhysique",
              "TypeAssociationRessourcePhysique","RessourcePhysiqueUnitaire","RessourcePhysiqueMesurable",
              "AssociationRessourcePhysique","AssociationRessourceStructurelle","CaracteristiqueElement",
              "CaracteristiqueSymbole","LigneProduit","RessourceStructurelle","ProvenanceObjet",
              "TypeProvenance","Objectchecksum"]:
        b.lier_gamme_classe(G1, c)

    # ==================================================================
    # G2 — RessourceInstallationFixe V1
    # ==================================================================
    G2 = "RessourceInstallationFixe"
    b.merge_gamme(G2, "V1", "2025-09-22")

    b.merge_enum("EnumIndicateurLigneVoie", ["LIGNE", "VOIE", "NON_APPLICABLE"])

    b.merge_classe("TypeInstallationFixe",
        description="Type référentiel d'une IFX. Si le type évolue, il faut borner et recréer l'IFX liée.",
        attributs=[
            {"nom": "code",        "type": "P-String"},
            {"nom": "mnemo",       "type": "P-String"},
            {"nom": "indicLigVoi", "type": "EnumIndicateurLigneVoie"},
        ])

    b.merge_classe("RelationRessourceInstallationFixe", abstraite=True,
        description="Lien entre deux IFX. DDA=max(DDA IFX), DFA=min(DFA IFX).")
    b.merge_classe("RelationRessourceInstallationFixeOrdonnee",
        attributs=[{"nom": "rang", "type": "P-Integer", "description": "Rang d'ordonnancement."}])
    b.merge_classe("RelationRessourceInstallationFixeDeleguee",  abstraite=True)
    b.merge_classe("RelationRessourceInstallationFixeCommandee", abstraite=True)
    b.merge_classe("RelationRessourceInstallationFixeExtremite", abstraite=True)
    b.merge_classe("RelationRessourceInstallationFixeControlee", abstraite=True)
    b.merge_classe("TypeRelationRessourceInstallationFixe",
        attributs=[{"nom": "code"}, {"nom": "libelle"}])
    b.merge_classe("RelationExtremiteLiaison")
    b.merge_classe("RelationInstallationFixeComposant")
    b.merge_classe("RelationMiseEnOeuvre")
    b.merge_classe("RelationResourceIFxAlimentationDisponible")
    b.merge_classe("RelationResourceIFxAlimentationSecours")
    b.merge_classe("RelationResourceFxAlimentationNormale")
    b.merge_classe("ImplantationMultiPonctuelle",
        description="Implantation composée de plusieurs points géographiques.")

    for src, tgt in [
        ("RelationRessourceInstallationFixeOrdonnee",  "RelationRessourceInstallationFixe"),
        ("RelationRessourceInstallationFixeDeleguee",  "RelationRessourceInstallationFixe"),
        ("RelationRessourceInstallationFixeCommandee", "RelationRessourceInstallationFixe"),
        ("RelationRessourceInstallationFixeExtremite", "RelationRessourceInstallationFixe"),
        ("RelationRessourceInstallationFixeControlee", "RelationRessourceInstallationFixe"),
        ("RelationExtremiteLiaison",                   "RelationRessourceInstallationFixeOrdonnee"),
        ("RelationInstallationFixeComposant",          "RelationRessourceInstallationFixeOrdonnee"),
        ("RelationMiseEnOeuvre",                       "RelationRessourceInstallationFixe"),
        ("RelationResourceIFxAlimentationDisponible",  "RelationRessourceInstallationFixe"),
        ("RelationResourceIFxAlimentationSecours",     "RelationRessourceInstallationFixe"),
        ("RelationResourceFxAlimentationNormale",      "RelationRessourceInstallationFixe"),
        ("ImplantationMultiPonctuelle",                "ImplantationAbstraite"),
    ]:
        b.add_relation(src, "HERITE_DE", tgt)

    b.add_relation("RessourceInstallationFixe", "TYPE_PAR",    "TypeInstallationFixe",
                   role="typeInstallationFixe", cardinalite="1..1")
    b.add_relation("RessourceInstallationFixe", "COMPOSE_DE",  "RelationRessourceInstallationFixe",
                   role="relationsInstallationsFixes", cardinalite="0..*")
    b.add_relation("RelationRessourceInstallationFixe", "TYPE_PAR", "TypeRelationRessourceInstallationFixe",
                   role="typeRelation")
    b.add_relation("RessourceInstallationFixe", "A_POUR_IMPLANTATION", "ImplantationMultiPonctuelle")

    for c in ["RessourceInstallationFixe","TypeInstallationFixe",
              "RelationRessourceInstallationFixe","RelationRessourceInstallationFixeOrdonnee",
              "RelationRessourceInstallationFixeDeleguee","RelationRessourceInstallationFixeCommandee",
              "RelationRessourceInstallationFixeExtremite","RelationRessourceInstallationFixeControlee",
              "TypeRelationRessourceInstallationFixe","RelationExtremiteLiaison",
              "RelationInstallationFixeComposant","RelationMiseEnOeuvre",
              "RelationResourceIFxAlimentationDisponible","RelationResourceIFxAlimentationSecours",
              "RelationResourceFxAlimentationNormale","ImplantationAbstraite","ImplantationMultiPonctuelle"]:
        b.lier_gamme_classe(G2, c)
    # ==================================================================
    # G3 — Topologie V0.2 (CORRIGÉE & UNIFIÉE VIA XML)
    # ==================================================================
    G3 = "Topologie"
    b.merge_gamme(G3, "V0.2", "2026-07-02")

    # Concepts de Parcours (Logique)
    b.merge_classe("RessourceParcoursTopologique", abstraite=False,
        description="Représente une ligne ou une voie. Hérite de RessourceAbstraiteNommee. Composée d'états datés.")
    
    b.merge_classe("RessourceParcoursTopologiqueADate", abstraite=False,
        description="État daté d'un parcours topologique (Voie/Ligne). Contient les relations vers les éléments physiques.")
    
    # LE PONT MANQUANT : La classe pivot extraite des XML
    b.merge_classe("RelationParcoursElementTopologique", abstraite=False,
        description="Classe pivot faisant le lien technique et temporel entre l'état d'une Voie et son tronçon physique (ETLV).")

    # Concepts Physiques et Linéaires
    b.merge_classe("ElémentTopologiqueOrienté", abstraite=True,
        description="Ressource abstraite topologique. Liée à au moins un SystemeReperagePk.")
    
    b.merge_classe("ElémentTopologiqueLinéaire", abstraite=True,
        description="Portion continue du réseau entre deux nœuds. Possède un pkDebut et un pkFin datés.")
    
    b.merge_classe("ElementTopologiqueLineaireVoie", abstraite=False,
        description="ETLV — Tronçon physique et continu de voie entre deux appareils de voie ou extrémités.")
    
    b.merge_classe("ElementTopologiqueLineaireLigne", abstraite=False,
        description="ETLL — Tronçon continu de ligne entre deux nœuds de ligne.")

    # Objets Métier Terminaux
    b.merge_classe("Voie", abstraite=False,
        description="Chemin de roulement identifié par un nom unique sur toute sa longueur (6 caractères max).")
    
    b.merge_classe("Ligne", abstraite=False,
        description="Voie ferrée entre un point origine et un point destination régie par arrêté préfectoral.",
        attributs=[
            {"nom": "code",            "type": "P-String", "description": "Code 6 caractères SNCF.", "obligatoire": True},
            {"nom": "libelle",         "type": "P-String", "obligatoire": True},
            {"nom": "dateAttribution", "type": "P-Datetime"},
            {"nom": "reserve",         "type": "P-Boolean"},
        ])

    b.merge_classe("TypeDeVoie",     attributs=[{"nom": "mnemo", "description": "VPL, VS ou VPA."}])
    b.merge_classe("TypeLigne",      attributs=[{"nom": "code"}, {"nom": "mnemo"}])
    b.merge_classe("VoieDeLigne",    description="Voie associée à une ligne ferroviaire.")
    b.merge_classe("VoieDeSaf",      description="Voie associée à un SAF.")
    b.merge_classe("ExtremiteVoie",  description="Extrémité d'une voie, liée à une ExtrémitéRéseau.")
    b.merge_classe("ExtrémitéRéseau", description="Extrémité physique ou virtuelle d'un tronçon.")
    b.merge_classe("TypeExtremiteReseau", attributs=[{"nom": "mnemo", "type": "P-String"}])
    b.merge_classe("TroncCommun",    description="Deux lignes partageant une portion d'une même voie.")
    b.merge_classe("RessourceConnexionOrientee", description="Arc du graphe de connexité entre deux éléments topologiques.",
        attributs=[{"nom": "navigabilite", "type": "P-String"}])
    b.merge_classe("MouvementPossible", description="Mouvement possible associé à une RCO.",
        attributs=[{"nom": "mouvement", "type": "P-String"}])

    # --- ARBRE D'HÉRITAGE (Inchangé mais consolidé) ---
    for src, tgt in [
        ("ElémentTopologiqueOrienté",       "RessourceAbstraite"),
        ("ElémentTopologiqueLinéaire",      "ElémentTopologiqueOrienté"),
        ("ExtrémitéRéseau",                 "ElémentTopologiqueOrienté"),
        ("ElementTopologiqueLineaireLigne", "ElémentTopologiqueLinéaire"),
        ("ElementTopologiqueLineaireVoie",  "ElémentTopologiqueLinéaire"),
        ("Ligne",                           "RessourceParcoursTopologique"),
        ("Voie",                            "RessourceParcoursTopologique"),
        ("VoieDeLigne",                     "Voie"),
        ("VoieDeSaf",                       "Voie"),
        ("RessourceParcoursTopologique",    "RessourceAbstraiteNommee"),
        ("MouvementPossible",               "ElementADateAbstrait"),
        ("RelationParcoursElementTopologique", "ElementADateAbstrait"), # Héritage de la nouvelle pièce
    ]:
        b.add_relation(src, "HERITE_DE", tgt)

    # --- LES RELATIONS STRUCTURELLES DE LA GAMME ---
    b.add_relation("Ligne", "TYPE_PAR", "TypeLigne")
    b.add_relation("Voie",  "TYPE_PAR", "TypeDeVoie")
    b.add_relation("ExtremiteVoie",   "ASSOCIE_A", "ExtrémitéRéseau")
    b.add_relation("ExtrémitéRéseau", "TYPE_PAR",  "TypeExtremiteReseau")
    b.add_relation("RessourceConnexionOrientee", "COMPOSE_DE", "MouvementPossible", role="mouvements")

    # --- LE NOUVEAU PONT TOPOLOGIQUE REBOUCHÉ  
    # 1. Le parcours englobe ses versions temporelles
    b.add_relation("RessourceParcoursTopologique", "COMPOSE_DE", "RessourceParcoursTopologiqueADate", role="etatsADate")
    # 2. L'état temporel se décompose en liens vers le physique
    b.add_relation("RessourceParcoursTopologiqueADate", "COMPOSE_DE", "RelationParcoursElementTopologique", role="elementsTopologiques")
    # 3. La relation pivot pointe enfin sur le tronçon de rail physique (ETLV)
    b.add_relation("RelationParcoursElementTopologique", "ASSOCIE_A", "ElementTopologiqueLineaireVoie", role="elementAssocie")

    b.add_relation("ElementTopologiqueLineaireVoie", "ASSOCIE_A", "Voie", role="appartientALaVoie")

    # Liaison systématique à la Gamme
    for c in ["RessourceParcoursTopologique","RessourceParcoursTopologiqueADate",
              "RessourceConnexionOrientee","MouvementPossible","ElémentTopologiqueOrienté",
              "ElémentTopologiqueLinéaire","ExtrémitéRéseau","TypeExtremiteReseau",
              "ElementTopologiqueLineaireLigne","Ligne","TypeLigne","TroncCommun",
              "ElementTopologiqueLineaireVoie","Voie","TypeDeVoie","VoieDeLigne",
              "VoieDeSaf","ExtremiteVoie", "RelationParcoursElementTopologique"]:
        b.lier_gamme_classe(G3, c)

    # ==================================================================
    # G4 — Système de repérage V1
    # ==================================================================
    G4 = "Système de repérage"
    b.merge_gamme(G4, "V1", "2025-03-27")

    b.merge_enum("EnumTypeAnomalie", ["V", "S", "A"])

    b.merge_classe("SystemeReperage", abstraite=True,
        description="Permet de déterminer la position d'un objet dans un repère défini. Toujours topologiquement continu.")
    b.merge_classe("SystemeReperagePk",
        description="SR à base de points kilométriques. pkDebut < pkFin.",
        attributs=[
            {"nom": "pkDebut", "type": "P-Long", "description": "PK début au format interne GAIA.", "obligatoire": True},
            {"nom": "pkFin",   "type": "P-Long", "description": "PK fin au format interne GAIA.",  "obligatoire": True},
        ])
    b.merge_classe("AnomalieSR",
        description="Anomalie kilométrique d'un SR (distance, suppression, ajout de RK).",
        attributs=[
            {"nom": "rkPrecedent",   "type": "P-Integer"},
            {"nom": "typeAnomalie",  "type": "EnumTypeAnomalie",
             "description": "V=distance≠1000m, S=suppression RK, A=ajout RK."},
            {"nom": "valeur",        "type": "P-Integer",
             "description": "0 pour ajout/suppression, valeur de distance sinon."},
        ])
    b.merge_classe("SystemeReperageAdministratif",
        description="SR donné à la création de la ligne par décret ministériel.")
    b.merge_classe("SystemeReperageLigne",
        description="SR physique d'une ligne. Ordonné par rang.",
        attributs=[{"nom": "rang", "type": "P-Integer", "description": "Ordre dans la séquence des SR ligne.", "obligatoire": True}])
    b.merge_classe("SystemeReperageVoie",
        description="SR d'une voie. Libellé = nom voie + communes extrémités.")
    b.merge_classe("SystemeReperageVoieDeSaf",
        description="SR d'une voie de SAF.")
    b.merge_classe("SystemeReperageVoieDeLigne",
        description="SR d'une voie de ligne. Possède pkProjeteDebut et pkProjeteFin.",
        attributs=[
            {"nom": "pkProjeteDebut", "type": "P-Long"},
            {"nom": "pkProjeteFin",   "type": "P-Long"},
        ])
    b.merge_classe("SystemeReperageCurviligne",
        description="Repère à une dimension continu. Origine à 0 m.",
        attributs=[
            {"nom": "libelle",  "type": "P-String", "description": "Nom du segment."},
            {"nom": "pkDebut",  "type": "P-Long"},
            {"nom": "pkFin",    "type": "P-Long"},
        ])
    b.merge_classe("SystemeReperageGeodesique",
        description="Repère tridimensionnel (X,Y,Z). Ex : RGF93 / Lambert 93.")
    b.merge_classe("RepereDeCalibragePkGeo",
        description="Bijection entre SR PK et SR géodésique. Composé de PointsDeCalibrage.")
    b.merge_classe("PointDeCalibragePK",
        description="Point de calibrage PK avec coordonnées géodésiques (X,Y,Z) et localisation PK.",
        attributs=[
            {"nom": "libelle", "type": "P-String"},
            {"nom": "exclu",   "type": "P-Boolean"},
        ])
    b.merge_classe("PointDeCalibrageIFX",
        description="Point de calibrage lié à une installation fixe et l'une de ses implantations ponctuelles.")

    for src, tgt in [
        ("SystemeReperage",             "RessourceAbstraiteNommee"),
        ("SystemeReperagePk",           "SystemeReperage"),
        ("SystemeReperageAdministratif","SystemeReperagePk"),
        ("SystemeReperageLigne",        "SystemeReperagePk"),
        ("SystemeReperageVoie",         "SystemeReperagePk"),
        ("SystemeReperageVoieDeSaf",    "SystemeReperageVoie"),
        ("SystemeReperageVoieDeLigne",  "SystemeReperageVoie"),
        ("AnomalieSR",                  "RessourceAbstraite"),
        ("RepereDeCalibragePkGeo",      "RessourceAbstraiteNommee"),
        ("PointDeCalibragePK",          "ObjetPersistant"),
        ("PointDeCalibrageIFX",         "PointDeCalibragePK"),
    ]:
        b.add_relation(src, "HERITE_DE", tgt)

    b.add_relation("SystemeReperagePk",    "COMPOSE_DE", "AnomalieSR",          role="anomalies", cardinalite="0..*")
    b.add_relation("SystemeReperageLigne", "ASSOCIE_A",  "SystemeReperageAdministratif", role="srlAdministratif")
    b.add_relation("RepereDeCalibragePkGeo", "ASSOCIE_A", "SystemeReperageGeodesique")
    b.add_relation("RepereDeCalibragePkGeo", "ASSOCIE_A", "SystemeReperagePk")
    b.add_relation("RepereDeCalibragePkGeo", "COMPOSE_DE","PointDeCalibragePK", cardinalite="2..*")
    b.add_relation("PointDeCalibrageIFX",    "ASSOCIE_A", "RessourceInstallationFixe")
    # SystemeReperagePk associé à ses anomalies
    b.add_relation("SystemeReperagePk", "COMPOSE_DE", "AnomalieSR", role="anomalies")
    # SystemeReperageLigne associé à son SR administratif
    b.add_relation("SystemeReperageLigne", "ASSOCIE_A", "SystemeReperageAdministratif")

    for c in ["SystemeReperage","SystemeReperagePk","AnomalieSR","SystemeReperageAdministratif",
              "SystemeReperageLigne","SystemeReperageVoie","SystemeReperageVoieDeSaf",
              "SystemeReperageVoieDeLigne","SystemeReperageCurviligne","SystemeReperageGeodesique",
              "RepereDeCalibragePkGeo","PointDeCalibragePK","PointDeCalibrageIFX"]:
        b.lier_gamme_classe(G4, c)

    # ==================================================================
    # G5 — Localisation et Implantation V0
    # ==================================================================
    G5 = "Localisation et Implantation"
    b.merge_gamme(G5, "V0", "2025-03-24")

    b.merge_classe("LocalisationSR", abstraite=True,
        description="Localisation selon un système de repérage. Toujours caractérisée par DDA et DFA.")
    b.merge_classe("LocalisationPk",
        description="Localisation ponctuelle par point kilométrique.",
        attributs=[
            {"nom": "pk",                  "type": "P-Long", "description": "PK au format interne GAIA."},
            {"nom": "sensLecture",         "type": "P-String", "defaut": "Bidirectionnel", "obligatoire": True},
            {"nom": "indicCalcule",        "type": "P-String", "defaut": "N", "obligatoire": True},
            {"nom": "indicFiable",         "type": "P-String", "defaut": "O", "obligatoire": True},
            {"nom": "indicPkFictif",       "type": "P-String", "defaut": "N", "obligatoire": True},
            {"nom": "origineLocalisation", "type": "P-String", "description": "IF, IF_PR, PR ou NA.", "obligatoire": True},
            {"nom": "positionLocalisation","type": "P-String", "defaut": "NA"},
            {"nom": "nomVoie",             "type": "P-String", "description": "Redondant avec la voie du SR, vide par défaut."},
        ])
    b.merge_classe("LocalisationCartographique",
        description="Localisation géographique (X,Y,Z) dans un SR géodésique.",
        attributs=[
            {"nom": "coordonneeX", "type": "P-Double"},
            {"nom": "coordonneeY", "type": "P-Double"},
            {"nom": "coordonneeZ", "type": "P-Double"},
        ])
    b.merge_classe("LocalisationGeometrique",
        description="Localisation géométrique (X,Y,Z) dans un SR nul. Ex: profil en long routier d'un PN.",
        attributs=[
            {"nom": "coordonneeX", "type": "P-Double"},
            {"nom": "coordonneeY", "type": "P-Double"},
            {"nom": "coordonneeZ", "type": "P-Double"},
        ])

    b.merge_classe("ImplantationInstallationFixe",
        description="Implantation sur/dans une ou plusieurs RessourceInstallationFixe. Composée de RelationImplantationInstallationFixe datées.")
    b.merge_classe("ImplantationGeometrique",
        description="Implantation composée d'une collection datée de localisations géométriques.")
    b.merge_classe("ImplantationLineaireSRPK",
        description="Implantation linéaire pour objets non liés à des éléments topologiques. Définie par pkDebut, pkFin, sens et un SR PK.",
        attributs=[{"nom": "sens", "type": "P-String"}])
    b.merge_classe("ImplantationPonctuelleSRPK",
        description="Implantation ponctuelle pour objets non liés à des éléments topologiques. Définie par pk, sens et un SR PK.",
        attributs=[{"nom": "sens", "type": "P-String"}])
    b.merge_classe("ImplantationCartographique",
        description="Situe un objet sur une carte. Composée d'une collection datée de LocalisationCartographique.")
    b.merge_classe("ImplantationPonctuelle",
        description="Implantation ponctuelle liée à un ETLL ou ETLV. Composée d'une LocalisationPk.")
    b.merge_classe("ImplantationTopologiqueLineaire",
        description="Implantation pour objets directement liés à des éléments topologiques. Composée de RelationImplantationRessourceTopologique avec pkMin/pkMax et sens.")
    b.merge_classe("ImplantationRessourceParcoursInfrastructure",
        description="Implantation sur une voie ou une ligne (RessourceParcoursInfrastructure).")
    b.merge_classe("ImplantationLineaireRessourceParcoursInfrastructure",
        description="Implantation linéaire sur une voie/ligne. Composée de RelationRessourceParcoursInfrastructure ordonnées.")

    for src, tgt in [
        ("LocalisationSR",   "ElementADateAbstrait"),
        ("LocalisationPk",   "LocalisationSR"),
        ("LocalisationCartographique", "LocalisationSR"),
        ("LocalisationGeometrique",    "LocalisationSR"),
        ("ImplantationAbstraite",      "RessourceAbstraite"),
        ("ImplantationInstallationFixe",   "ImplantationAbstraite"),
        ("ImplantationGeometrique",        "ImplantationAbstraite"),
        ("ImplantationLineaireSRPK",       "ImplantationAbstraite"),
        ("ImplantationPonctuelleSRPK",     "ImplantationAbstraite"),
        ("ImplantationCartographique",     "ImplantationAbstraite"),
        ("ImplantationPonctuelle",         "ImplantationAbstraite"),
        ("ImplantationTopologiqueLineaire","ImplantationAbstraite"),
        ("ImplantationRessourceParcoursInfrastructure",         "ImplantationAbstraite"),
        ("ImplantationLineaireRessourceParcoursInfrastructure", "ImplantationRessourceParcoursInfrastructure"),
    ]:
        b.add_relation(src, "HERITE_DE", tgt)

    b.add_relation("LocalisationPk",             "TYPE_PAR",  "SystemeReperagePk")
    b.add_relation("LocalisationCartographique",  "TYPE_PAR",  "SystemeReperageGeodesique")
    b.add_relation("ImplantationPonctuelle",      "COMPOSE_DE","LocalisationPk")
    b.add_relation("ImplantationInstallationFixe","COMPOSE_DE","RessourceInstallationFixe",
                   role="relationsImplantation", cardinalite="1..*")
    b.add_relation("ImplantationPonctuelleSRPK", "TYPE_PAR",   "SystemeReperagePk")
    b.add_relation("ImplantationLineaireSRPK",   "TYPE_PAR",   "SystemeReperagePk")
    b.add_relation("ImplantationCartographique", "COMPOSE_DE", "LocalisationCartographique")
    b.add_relation("ImplantationGeometrique",    "COMPOSE_DE", "LocalisationGeometrique")
    b.add_relation("LocalisationCartographique", "TYPE_PAR",   "SystemeReperageGeodesique")
    b.add_relation("ImplantationPonctuelleSRPK", "TYPE_PAR",   "SystemeReperagePk")
    b.add_relation("ImplantationLineaireSRPK",   "TYPE_PAR",   "SystemeReperagePk")
    b.add_relation("ImplantationCartographique", "COMPOSE_DE", "LocalisationCartographique")
    b.add_relation("ImplantationGeometrique",    "COMPOSE_DE", "LocalisationGeometrique")
    b.add_relation("ImplantationPonctuelle",     "COMPOSE_DE", "LocalisationPk")

    for c in ["LocalisationSR","LocalisationPk","LocalisationCartographique","LocalisationGeometrique",
              "ImplantationAbstraite","ImplantationInstallationFixe","ImplantationGeometrique",
              "ImplantationLineaireSRPK","ImplantationPonctuelleSRPK","ImplantationCartographique",
              "ImplantationPonctuelle","ImplantationMultiPonctuelle","ImplantationTopologiqueLineaire",
              "ImplantationRessourceParcoursInfrastructure","ImplantationLineaireRessourceParcoursInfrastructure"]:
        b.lier_gamme_classe(G5, c)

    # ==================================================================
    # G6 — SAF V1
    # ==================================================================
    G6 = "SAF"
    b.merge_gamme(G6, "V1", "2024-12-05")

    b.merge_enum("EnumTypeSaf", ["ITE", "CHANTIER", "EIM", "ET", "TRIAGE"])
    b.merge_enum("EnumCategorieCommerciale", ["C1", "C2", "C3", "C4"])

    b.merge_classe("SAF",
        description="Secteur d'Activité Ferroviaire. Zone géographique du réseau avec voies de service et fonctions ferroviaires.",
        attributs=[
            {"nom": "libelle",              "type": "P-String",  "obligatoire": True},
            {"nom": "categorieCommerciale", "type": "EnumCategorieCommerciale"},
            {"nom": "commentaireAccessibilite", "type": "P-String"},
            {"nom": "commentaireOrientation",   "type": "P-String"},
            {"nom": "commentaireOuverture",     "type": "P-String"},
        ])
    b.merge_classe("TypeSaf",      attributs=[{"nom": "mnemo", "type": "EnumTypeSaf", "obligatoire": True}])
    b.merge_classe("TypeSafADate", description="Lien daté entre un SAF et son TypeSaf. Cycle de vie inclus dans celui du SAF.")
    b.merge_classe("RelationSafPere",
        description="Composition SAF père / sous-SAF. Datée par DDA/DFA.",
        attributs=[{"nom": "dateDebutActivite", "type": "P-Datetime"}, {"nom": "dateFinActivite", "type": "P-Datetime"}])
    b.merge_classe("RelationIdentifiantSaf",      abstraite=True,
        description="Rattachement d'un SAF à un autre SAF ou à une gare. Daté.")
    b.merge_classe("RelationIdentifiantSafSaf",   description="Rattachement d'un SAF à un autre SAF.")
    b.merge_classe("RelationIdentifiantSafGare",  description="Rattachement d'un SAF à une gare.")
    b.merge_classe("RegionSNCF",   description="Région SNCF à laquelle un SAF peut être rattaché.")

    b.add_relation("SAF",                      "HERITE_DE", "ElémentTopologiqueOrienté")
    b.add_relation("RelationIdentifiantSafSaf", "HERITE_DE","RelationIdentifiantSaf")
    b.add_relation("RelationIdentifiantSafGare","HERITE_DE","RelationIdentifiantSaf")
    b.add_relation("SAF", "COMPOSE_DE", "TypeSafADate",      role="typeSafADate", cardinalite="1..*")
    b.add_relation("TypeSafADate", "TYPE_PAR", "TypeSaf")
    b.add_relation("SAF", "COMPOSE_DE", "RelationSafPere",   role="sousSafs")
    b.add_relation("SAF", "AGREGE",     "RelationIdentifiantSaf", role="rattachement")
    b.add_relation("SAF", "ASSOCIE_A",  "RegionSNCF")

    for c in ["SAF","TypeSaf","TypeSafADate","RelationSafPere",
              "RelationIdentifiantSaf","RelationIdentifiantSafSaf","RelationIdentifiantSafGare","RegionSNCF"]:
        b.lier_gamme_classe(G6, c)

    # ==================================================================
    # G7 — Représentation géométrique d'un élément topologique V0.1
    # ==================================================================
    G7 = "Représentation géométrique d'un élément topologique"
    b.merge_gamme(G7, "V0.1", "2024-10-03")

    b.merge_classe("RessourceGeometrieAbstraite", abstraite=True,
        description="Classe abstraite des représentations géométriques. Porte DDA et DFA de la représentation.")
    b.merge_classe("GTIV",
        description="Représentation géométrique d'un élément topologique de voie (GTI Voie). Immuable sauf correction.")
    b.merge_classe("GTIL",
        description="Représentation géométrique d'un élément topologique de ligne (GTI Ligne). Immuable sauf correction.")

    for src, tgt in [
        ("RessourceGeometrieAbstraite", "RessourceAbstraite"),
        ("GTIV", "RessourceGeometrieAbstraite"),
        ("GTIL", "RessourceGeometrieAbstraite"),
    ]:
        b.add_relation(src, "HERITE_DE", tgt)

    b.add_relation("GTIV", "ASSOCIE_A", "ElementTopologiqueLineaireVoie",
                   role="ressource", cardinalite="1..1")
    b.add_relation("GTIL", "ASSOCIE_A", "ElementTopologiqueLineaireLigne",
                   role="ressource", cardinalite="1..1")
    # ElémentTopologiqueLinéaire composé de pkDebut et pkFin
    b.add_relation("ElémentTopologiqueLinéaire", "COMPOSE_DE", "LocalisationPk", role="pkDebut")
    b.add_relation("ElémentTopologiqueLinéaire", "COMPOSE_DE", "LocalisationPk", role="pkFin")
    # ElémentTopologiqueOrienté lié à une collection de SystemeReperagePk
    b.add_relation("ElémentTopologiqueOrienté", "ASSOCIE_A", "SystemeReperagePk")
    # ExtrémitéRéseau liée à un unique TypeExtremiteReseau
    b.add_relation("ExtrémitéRéseau", "TYPE_PAR", "TypeExtremiteReseau")

    for c in ["RessourceGeometrieAbstraite","GTIV","GTIL"]:
        b.lier_gamme_classe(G7, c)

    # ==================================================================
    # G8 — Repère de calibrage V0.1
    # ==================================================================
    G8 = "Repère de calibrage"
    b.merge_gamme(G8, "V0.1", "2024-10-03")

    b.merge_classe("RepereDeCalibragePkGeo",
        description="Bijection entre SR PK et SR géodésique. Immuable sauf correction.")
    
    b.add_relation("RepereDeCalibragePkGeo", "ASSOCIE_A",  "SystemeReperagePk")
    b.add_relation("RepereDeCalibragePkGeo", "ASSOCIE_A",  "SystemeReperageGeodesique")
    b.add_relation("PointDeCalibrageIFX",    "ASSOCIE_A",  "RessourceInstallationFixe")
    b.add_relation("PointDeCalibrageIFX",    "ASSOCIE_A",  "ImplantationPonctuelle")

    for c in ["RepereDeCalibragePkGeo","PointDeCalibragePK","PointDeCalibrageIFX",
              "SystemeReperagePk","SystemeReperageGeodesique"]:
        b.lier_gamme_classe(G8, c)

    # ==================================================================
    # G9 — Passage à Niveau V9
    # ==================================================================
    G9 = "Passage à Niveau"
    b.merge_gamme(G9, "V9", "2025-11-17")

    b.merge_enum("EnumClassePN", [
        "00","10","11","12","13","14","15","16","17","18","19",
        "20","21","31","32","41","42","43","44","45","46"])
    b.merge_enum("EnumNiveauAcceleration", ["NE2","NE3","NE4","E2","E3","E4","GV2","GV3","GV4"])
    b.merge_enum("EnumParitePN", ["PAIR","IMPAIR"])

    b.merge_classe("PassageANiveau",
        description="Passage à niveau ferroviaire. InstallationFixe avec implantation ponctuelle ligne et géodésique.",
        attributs=[
            {"nom": "codeLigneDesignation",              "type": "P-String",  "obligatoire": True,
             "description": "Calculé automatiquement depuis l'implantation."},
            {"nom": "delaiReelFermetureCroissant",       "type": "P-Integer", "description": "En secondes."},
            {"nom": "delaiReelFermetureDecroissant",     "type": "P-Integer", "description": "En secondes."},
            {"nom": "delaiTheoriqueFermeture",           "type": "P-Integer", "description": "En secondes. Schéma DEX."},
            {"nom": "dureemaxFermeture",                 "type": "P-Integer", "description": "En secondes."},
            {"nom": "preoccupant",                       "type": "P-Boolean", "obligatoire": True,
             "description": "PN inscrit au programme national de sécurisation. Calculé automatiquement."},
            {"nom": "circulationConception",             "type": "P-Integer", "obligatoire": True},
            {"nom": "indicDifficulteFranchissement",     "type": "P-Boolean", "obligatoire": True,
             "description": "Calculé depuis résultat Tipule."},
            {"nom": "indicPlaqueGAMEC",                 "type": "P-Boolean", "obligatoire": True},
            {"nom": "indicTelephone",                   "type": "P-Boolean", "obligatoire": True},
            {"nom": "indicZoneHumide",                  "type": "P-String",  "defaut": "non renseigné", "obligatoire": True},
            {"nom": "largeur",                          "type": "P-Double",  "description": "En mètres.", "obligatoire": True},
            {"nom": "longueurTraversee",                "type": "P-Double",  "description": "En mètres.", "obligatoire": True},
            {"nom": "momentProduitTrainCirculationConception","type": "P-Long", "obligatoire": True,
             "description": "Produit circulations ferroviaires × circulations routières journalières."},
            {"nom": "visibiliteCroissanteEnMetre",      "type": "P-Double",  "obligatoire": True},
            {"nom": "visibiliteDecroissanteEnMetre",    "type": "P-Double",  "obligatoire": True},
            {"nom": "visibiliteCroissanteEnSeconde",    "type": "P-Double",  "obligatoire": True},
            {"nom": "visibiliteDecroissanteEnSeconde",  "type": "P-Double",  "obligatoire": True},
        ])

    b.merge_classe("NiveauAccelerationIfx",
        description="Propriété facultative du PN. Hérite de AssociationProprieteRessource.",
        attributs=[{"nom": "parite", "type": "EnumParitePN", "description": "PAIR ou IMPAIR."}])
    b.merge_classe("NiveauAcceleration",
        attributs=[{"nom": "niveau", "type": "EnumNiveauAcceleration", "obligatoire": True}])
    b.merge_classe("AssociationProprieteRessource",
        description="Lien daté entre une RessourceAbstraite et un TypePropriete.")
    b.merge_classe("TypePropriete",
        description="Type de propriété référentiel (ex: NiveauAcceleration, ProfilEnLongRoutier, technologie KVB…)",
        attributs=[{"nom": "code", "type": "P-String"}, {"nom": "libelle", "type": "P-String"}])

    b.merge_classe("ProfilEnLongRoutier",
        description="Profil routier d'un PN. DDA = date de levé topographique. Immuable sauf correction.",
        attributs=[
            {"nom": "margeGardeAuSol", "type": "P-Double", "obligatoire": True,
             "description": "Espace entre bas de caisse et point le plus haut du sol (marge au point critique)."},
            {"nom": "margePorteAFaux", "type": "P-Double", "obligatoire": True,
             "description": "Espace entre porte-à-faux avant et point le plus haut du sol."},
        ])
    b.merge_classe("ElementProfilRoutier",
        description="Élément d'un profil en long routier. Même DDA/DFA que son ProfilEnLongRoutier.",
        attributs=[
            {"nom": "abscisse",       "type": "P-Double"},
            {"nom": "altitude",       "type": "P-Double"},
            {"nom": "abscisseSurRail","type": "P-Boolean", "description": "OUI si l'élément a la particularité 'rail'."},
        ])

    b.add_relation("PassageANiveau",         "HERITE_DE", "RessourceInstallationFixe")
    b.add_relation("NiveauAccelerationIfx",  "HERITE_DE", "AssociationProprieteRessource")
    b.add_relation("ProfilEnLongRoutier",    "HERITE_DE", "RessourceAbstraite")
    b.add_relation("ElementProfilRoutier",   "HERITE_DE", "ElementADateAbstrait")
    b.add_relation("AssociationProprieteRessource", "HERITE_DE", "RessourceAbstraite")

    b.add_relation("PassageANiveau",       "AGREGE",     "NiveauAccelerationIfx",   role="niveauxAcceleration", cardinalite="0..*")
    b.add_relation("PassageANiveau",       "AGREGE",     "ProfilEnLongRoutier",      role="profilEnLong",        cardinalite="0..1")
    b.add_relation("NiveauAccelerationIfx","ASSOCIE_A",  "NiveauAcceleration")
    b.add_relation("AssociationProprieteRessource","TYPE_PAR","TypePropriete")
    b.add_relation("ProfilEnLongRoutier",  "COMPOSE_DE", "ImplantationAbstraite",   role="pkPointDepart",       cardinalite="1..1")
    b.add_relation("ProfilEnLongRoutier",  "COMPOSE_DE", "ElementProfilRoutier",    role="elements",            cardinalite="1..*")
    b.add_relation("PassageANiveau",        "A_POUR_IMPLANTATION", "ImplantationPonctuelle")
    b.add_relation("NiveauAccelerationIfx", "ASSOCIE_A",           "ImplantationAbstraite", role="origine")
    b.add_relation("NiveauAccelerationIfx", "ASSOCIE_A",           "ImplantationAbstraite", role="destination")

    for c in ["PassageANiveau","NiveauAccelerationIfx","NiveauAcceleration",
              "AssociationProprieteRessource","TypePropriete","ProfilEnLongRoutier","ElementProfilRoutier",
              "ImplantationInstallationFixe","ImplantationPonctuelle"]:
        b.lier_gamme_classe(G9, c)

    # ==================================================================
    # G10 — Point d'information ETCS V9
    # ==================================================================
    G10 = "Point d'information ETCS"
    b.merge_gamme(G10, "V9", "2024-10-24")

    b.merge_enum("EnumSensPI", ["C", "D"])
    b.merge_enum("EnumFonctionETCS", ["DA","DE","DS","RV","BR","RI","RG","CR","DR","VBC"])
    b.merge_enum("EnumTechnologieETCS", ["Commutable", "Fixe"])

    b.merge_classe("PointInformationETCS",
        description="Point d'information ETCS (PI). InstallationFixe sans implantation propre. "
                    "Identifié de manière unique par (numero, codeRegion). "
                    "Composé d'au moins deux balises ETCS ordonnées.",
        attributs=[
            {"nom": "sens",        "type": "EnumSensPI",   "obligatoire": True, "description": "C=Croissant, D=Décroissant."},
            {"nom": "chaine",      "type": "P-String",     "description": "O, N ou vide."},
            {"nom": "numero",      "type": "P-Integer",    "obligatoire": True, "description": "NID_BG — identifiant métier."},
            {"nom": "codeRegion",  "type": "P-Integer",    "obligatoire": True, "description": "NID_C — varie par région."},
        ])
    b.merge_classe("Eurobalise",
        description="Balise ETCS physique. LibelléE1..E8. Rang 0=position du PI. Implantation tous les 3m.",
        attributs=[{"nom": "dupliquee", "type": "P-String", "description": "OUI, NON ou NR."}])

    b.add_relation("PointInformationETCS", "HERITE_DE", "RessourceInstallationFixe")
    b.add_relation("Eurobalise",           "HERITE_DE", "RessourceInstallationFixe")
    b.add_relation("PointInformationETCS", "COMPOSE_DE", "Eurobalise",
                   role="balises", cardinalite="2..*")
    b.add_relation("PointInformationETCS", "AGREGE",    "RessourceInstallationFixe",
                   role="signalAssocie", cardinalite="0..*")
    b.add_relation("PointInformationETCS", "AGREGE",    "AssociationProprieteRessource",
                   role="fonctions", cardinalite="1..*")
    b.add_relation("Eurobalise",           "AGREGE",    "AssociationProprieteRessource",
                   role="technologie", cardinalite="1..1")

    for c in ["PointInformationETCS","Eurobalise","AssociationProprieteRessource","TypePropriete",
              "ImplantationPonctuelle","SystemeReperageVoie","SystemeReperageCurviligne"]:
        b.lier_gamme_classe(G10, c)

    # ==================================================================
    # G11 — Transit et Groupement de Zone V5
    # ==================================================================
    G11 = "Transit et Groupement de Zone"
    b.merge_gamme(G11, "V5", "2025-10-13")

    b.merge_enum("EnumPariteTransit", ["PAIR", "IMPAIR"])
    b.merge_enum("EnumTypeTransit",   ["Transit SNCF", "Transit Argos"])

    b.merge_classe("GroupementDeZone",
        description="Rassemblement d'une ou plusieurs zones de détection de même numéro dans un même poste. "
                    "RessourceInstallationFixe sans implantation.")
    b.merge_classe("ZoneDeDetection",
        description="Zone de détection de présence de circulation. "
                    "Cycle de vie indépendant du GroupementDeZone associé.")
    b.merge_classe("Transit",
        description="Asset logique orienté associé à un GroupementDeZone. "
                    "Mis en action par un itinéraire. RessourceInstallationFixe sans implantation.",
        attributs=[{"nom": "parite", "type": "EnumPariteTransit", "obligatoire": True,
                    "description": "P=Pair, I=Impair dans le libellé."}])
    b.merge_classe("TransitSNCF",  description="Transit SNCF standard.")
    b.merge_classe("TransitArgos", description="Transit Argos — toujours lié à un TransitSNCF. Libellé = SNCF + suffixe extrémités.")
    b.merge_classe("ContrainteTransit",
        description="Contrainte d'itinéraire associée à un transit. DDA=max(DDA transit, DDA itinéraire).",)
    b.merge_classe("Itineraire",
        description="Trajet identifié sur lequel les circulations peuvent se déplacer.")

    b.add_relation("GroupementDeZone", "HERITE_DE", "RessourceInstallationFixe")
    b.add_relation("Transit",          "HERITE_DE", "RessourceInstallationFixe")
    b.add_relation("TransitSNCF",      "HERITE_DE", "Transit")
    b.add_relation("TransitArgos",     "HERITE_DE", "Transit")
    b.add_relation("ContrainteTransit","HERITE_DE", "ElementADateAbstrait")

    b.add_relation("GroupementDeZone", "COMPOSE_DE", "ZoneDeDetection",
                   role="zonesDetection", cardinalite="1..*")
    b.add_relation("Transit",          "ASSOCIE_A",  "GroupementDeZone",
                   role="groupementZone", cardinalite="0..1")
    b.add_relation("TransitArgos",     "ASSOCIE_A",  "TransitSNCF",
                   role="transitSNCF", cardinalite="1..1")
    b.add_relation("ContrainteTransit","ASSOCIE_A",  "Transit",
                   role="transit", cardinalite="1..1")
    b.add_relation("Itineraire",       "COMPOSE_DE", "ContrainteTransit",
                   role="contraintesTransit", cardinalite="0..*")
    
    b.add_relation("Eurobalise", "AGREGE", "ImplantationPonctuelle", role="implantationVoie")
    b.add_relation("Eurobalise", "AGREGE", "ImplantationPonctuelle", role="implantationCurviligne")

    for c in ["GroupementDeZone","ZoneDeDetection","Transit","TransitSNCF","TransitArgos",
              "ContrainteTransit","Itineraire"]:
        b.lier_gamme_classe(G11, c)

    # ==================================================================
    # G12 — Point d'information KVB V6
    # ==================================================================
    G12 = "Point d'information KVB"
    b.merge_gamme(G12, "V6", "2025-01-30")

    b.merge_enum("EnumSensKVB",        ["A", "C", "D"])
    b.merge_enum("EnumTechnologieKVB", ["PI KVB analogique", "PI KVB numerique"])
    b.merge_enum("EnumTypeBaliseKVB",  ["B KVB numerique", "B KVB analogique", "B KVB marqueur"])
    b.merge_enum("EnumTechnologieBaliseKVB", ["Commutable", "Fixe"])

    b.merge_classe("PointInformationKVB",
        description="Ensemble de balises KVB transmettant un message à une circulation. "
                    "InstallationFixe sans implantation propre. "
                    "Au max 5 balises (analogique) ou 3 (numérique).",
        attributs=[{"nom": "sens", "type": "EnumSensKVB", "obligatoire": True,
                    "description": "A=Aucun, C=Croissant, D=Décroissant."}])
    b.merge_classe("BaliseKVB",
        description="Balise KVB physique. Libellé calculé = libellé PI + _A/_B/… "
                    "Toutes les balises d'un PI ont le même PK. Une seule balise marqueur par PI.",
        attributs=[{"nom": "sensLecture", "type": "P-String", "defaut": "Bidirectionnel"}])
    b.merge_classe("MessageKVB",
        description="Message transmis par un PointInformationKVB. Cycle de vie = celui du PI.")
    b.merge_classe("ChampInformationKVB",
        description="Information élémentaire dans un MessageKVB. DDA/DFA inclus dans ceux du PI.",
        attributs=[
            {"nom": "sens",          "type": "EnumSensKVB", "obligatoire": True,
             "description": "Sens de lecture du champ. C ou D uniquement (pas bidirectionnel)."},
            {"nom": "observation",   "type": "P-String"},
            {"nom": "declivite",     "type": "P-Double"},
            {"nom": "distanceBut",   "type": "P-Integer", "description": "Distance en amont/aval du point but."},
            {"nom": "indSortieVS",   "type": "P-Boolean", "description": "Vrai si paramétré depuis sortie voie de service."},
        ])
    b.merge_classe("TypeChampInformation",
        description="Type référentiel d'un champ d'information KVB. Code selon IG90169.",
        attributs=[{"nom": "code",  "type": "P-String", "obligatoire": True},
                   {"nom": "mnemo", "type": "P-String"}])
    b.merge_classe("PointBut",
        description="Point à partir duquel la vitesse but s'applique. "
                    "Peut être une IFX existante ou une IFX virtuelle si lié à un PK.")
    b.merge_classe("VitesseBut",     attributs=[{"nom": "vitesse", "type": "P-Integer"}])
    b.merge_classe("CategorieKVB",   attributs=[{"nom": "code",    "type": "P-String"}])

    b.add_relation("PointInformationKVB", "HERITE_DE", "RessourceInstallationFixe")
    b.add_relation("BaliseKVB",           "HERITE_DE", "RessourceInstallationFixe")
    b.add_relation("MessageKVB",          "HERITE_DE", "ElementADateAbstrait")
    b.add_relation("ChampInformationKVB", "HERITE_DE", "ElementADateAbstrait")
    b.add_relation("TypeChampInformation","HERITE_DE", "RessourceAbstraiteNommee")

    b.add_relation("PointInformationKVB", "COMPOSE_DE", "MessageKVB",
                   role="message", cardinalite="1..1")
    b.add_relation("PointInformationKVB", "COMPOSE_DE", "BaliseKVB",
                   role="balises", cardinalite="2..5")
    b.add_relation("PointInformationKVB", "AGREGE",     "RessourceInstallationFixe",
                   role="signalAssocie", cardinalite="0..*")
    b.add_relation("PointInformationKVB", "AGREGE",     "AssociationProprieteRessource",
                   role="technologie", cardinalite="1..1")
    b.add_relation("MessageKVB",          "COMPOSE_DE", "ChampInformationKVB",
                   role="champs", cardinalite="1..*")
    b.add_relation("ChampInformationKVB", "TYPE_PAR",   "TypeChampInformation")
    b.add_relation("ChampInformationKVB", "ASSOCIE_A",  "BaliseKVB", role="balise", cardinalite="1..1")
    b.add_relation("ChampInformationKVB", "AGREGE",     "PointBut",  role="pointBut", cardinalite="0..1")
    b.add_relation("ChampInformationKVB", "AGREGE",     "VitesseBut",role="vitesseBut")
    b.add_relation("VitesseBut",          "ASSOCIE_A",  "CategorieKVB")
    b.add_relation("BaliseKVB",              "AGREGE",     "ImplantationPonctuelle")
    b.add_relation("ImplantationPonctuelle", "COMPOSE_DE", "LocalisationPk")
    b.add_relation("LocalisationPk",         "TYPE_PAR",   "SystemeReperagePk")
    b.add_relation("BaliseKVB", "AGREGE", "ImplantationPonctuelle")
    b.add_relation("ImplantationPonctuelle", "COMPOSE_DE", "LocalisationPk")
    b.add_relation("LocalisationPk",         "TYPE_PAR",   "SystemeReperagePk")

    for c in ["PointInformationKVB","BaliseKVB","MessageKVB","ChampInformationKVB",
              "TypeChampInformation","PointBut","VitesseBut","CategorieKVB",
              "AssociationProprieteRessource","TypePropriete","ImplantationPonctuelle","SystemeReperageVoie"]:
        b.lier_gamme_classe(G12, c)

# ==================================================================
    # G13 — Habillage V1.0
    # ==================================================================
    G13 = "Habillage"
    b.merge_gamme(G13, "V1.0", "2025-02-18")

    # Énumérations
    b.merge_enum("EnumSensHabillage", ["D", "C", "B", "N"])

    # ------------------------------------------------------------------
    # 1. Référentiels (Refactoring hors coeur V3)
    # ------------------------------------------------------------------
    b.merge_classe("TypeHabillage",
        description="Référentiel principal des types d'habillage.",
        attributs=[
            {"nom": "code", "type": "P-String"},
            {"nom": "indicateurAffichage", "type": "P-String"},
            {"nom": "indicateurCartographie", "type": "P-String"},
            {"nom": "indicateurEntreprise", "type": "P-String"},
            {"nom": "indicateurICCc", "type": "P-String"},
            {"nom": "indicateurLimNoeud", "type": "P-String"},
            {"nom": "indicateurListValeur", "type": "P-String"},
            {"nom": "indicateurOuiNon", "type": "P-String"},
            {"nom": "indicateurRegionSncf", "type": "P-String"},
            {"nom": "indicateurSelection", "type": "P-String"},
            {"nom": "indicateurSens", "type": "P-String"},
            {"nom": "indicateurStructureAdministrative", "type": "P-String"},
            {"nom": "indicateurTypeDecoup", "type": "P-String"},
            {"nom": "indicateurVal", "type": "P-String"},
            {"nom": "mnemonique", "type": "P-String"},
            {"nom": "numNiv", "type": "P-Integer"},
            {"nom": "numOrdreAffichage", "type": "P-Integer"},
            {"nom": "typeLvd", "type": "P-String"},
            {"nom": "typeSdn", "type": "P-String"},
        ])

    b.merge_classe("HabillageTypeValeur",
        attributs=[
            {"nom": "code", "type": "P-String"},
            {"nom": "docOpposable", "type": "P-String"},
            {"nom": "mnemonique", "type": "P-String"},
            {"nom": "numDocumentOP", "type": "P-Integer"},
        ])

    b.merge_classe("TypeHabillageOriente",
        attributs=[{"nom": "code", "type": "P-String"}])

    b.merge_classe("TypeTension",
        attributs=[{"nom": "code", "type": "P-String"}])

    # ------------------------------------------------------------------
    # 2. Classes Métier (Topologie & Instances d'habillage)
    # ------------------------------------------------------------------
    b.merge_classe("HabillageOriente", abstraite=True,
        description="Classe mère de tous les habillages sur le réseau.",
        attributs=[
            {"nom": "oriente", "type": "P-Boolean"},
            {"nom": "sens", "type": "EnumSensHabillage"}
        ])

    # Sous-classes d'HabillageOriente
    b.merge_classe("HabillageValeur", attributs=[
        {"nom": "indCarto", "type": "P-String"},
        {"nom": "libelle", "type": "P-String"},
        {"nom": "libelle_2", "type": "P-String"}
    ])
    
    b.merge_classe("HabillageParcours")
    b.merge_classe("NomLocalDeVoie", attributs=[
        {"nom": "nomLocal", "type": "P-String"},
        {"nom": "nomThor", "type": "P-String"}
    ])
    b.merge_classe("HabillageRegle", attributs=[{"nom": "libelle", "type": "P-String"}])
    b.merge_classe("HabillageEntreprise")
    b.merge_classe("HabillageRegionSNCF")
    b.merge_classe("HabillageStructureAdministrative")
    b.merge_classe("HabillageCourantMaxCatenaire", attributs=[{"nom": "courantMax", "type": "P-Double"}])
    b.merge_classe("HabillageTension", attributs=[{"nom": "tesnion", "type": "P-Double"}]) # Graphie exacte de l'UML
    b.merge_classe("VitesseParCodeComposition", attributs=[{"nom": "libelle", "type": "P-String"}])


    # --- ARBRE D'HÉRITAGE ---
    for src, tgt in [
        ("TypeHabillage", "RessourceAbstraiteNommee"),
        ("HabillageTypeValeur", "RessourceAbstraiteNommee"),
        ("TypeHabillageOriente", "RessourceAbstraiteNommee"),
        ("TypeTension", "RessourceAbstraiteNommee"),
        ("HabillageOriente", "RessourceAbstraite"),
        ("HabillageValeur", "HabillageOriente"),
        ("HabillageParcours", "HabillageOriente"),
        ("NomLocalDeVoie", "HabillageOriente"),
        ("HabillageRegle", "HabillageOriente"),
        ("HabillageEntreprise", "HabillageOriente"),
        ("HabillageRegionSNCF", "HabillageOriente"),
        ("HabillageStructureAdministrative", "HabillageOriente"),
        ("HabillageCourantMaxCatenaire", "HabillageOriente"),
        ("HabillageTension", "HabillageOriente"),
        ("VitesseParCodeComposition", "HabillageOriente"),
    ]:
        b.add_relation(src, "HERITE_DE", tgt)


    # --- LES RELATIONS STRUCTURELLES ---
    
    # Hiérarchie TypeHabillage (Père/Enfant)
    b.add_relation("TypeHabillage", "ASSOCIE_A", "TypeHabillage", role="typeHabillagePere")
    
    # Liens HabillageOriente -> Référentiels
    b.add_relation("HabillageOriente", "TYPE_PAR", "TypeHabillage", role="typeHabillage")
    b.add_relation("HabillageOriente", "TYPE_PAR", "TypeHabillageOriente", role="type")
    
    # Lien HabillageOriente -> Localisation Géographique
    b.add_relation("HabillageOriente", "COMPOSE_DE", "LocalisationPk", role="localisationsPkDeb", cardinalite="1..*")
    b.add_relation("HabillageOriente", "COMPOSE_DE", "LocalisationPk", role="localisationsPkFin", cardinalite="1..*")

    # Relations spécifiques aux sous-classes
    b.add_relation("HabillageValeur", "AGREGE", "HabillageTypeValeur", role="valeur")
    b.add_relation("HabillageParcours", "ASSOCIE_A", "RessourceParcoursTopologique", role="parcoursInfrastructure")
    b.add_relation("HabillageEntreprise", "ASSOCIE_A", "Entreprise", role="entrepriseInterconnectee")
    b.add_relation("HabillageRegionSNCF", "ASSOCIE_A", "RegionSNCF", role="regionInterconnectee")
    b.add_relation("HabillageStructureAdministrative", "ASSOCIE_A", "StructureGeographique", role="structureInterconnectee")
    b.add_relation("HabillageTension", "TYPE_PAR", "TypeTension", role="typeTension")

    # Liaison systématique à la Gamme
    classes_g13 = [
        "TypeHabillage", "HabillageTypeValeur", "TypeHabillageOriente", "TypeTension",
        "HabillageOriente", "HabillageValeur", "HabillageParcours", "NomLocalDeVoie",
        "HabillageRegle", "HabillageEntreprise", "HabillageRegionSNCF", 
        "HabillageStructureAdministrative", "HabillageCourantMaxCatenaire", 
        "HabillageTension", "VitesseParCodeComposition"
    ]
    for c in classes_g13:
        b.lier_gamme_classe(G13, c)

    b.close()
    


if __name__ == "__main__":
    main()