from neo4j import GraphDatabase

URI = "bolt://127.0.0.1:7687"
USER = "neo4j"
PASSWORD = "db200402"


class UMLGraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run(self, query, **params):
        with self.driver.session() as session:
            session.run(query, **params)

    def create_constraints(self):
        self.run("CREATE CONSTRAINT classe_nom IF NOT EXISTS FOR (c:Classe) REQUIRE c.nom IS UNIQUE")
        self.run("CREATE CONSTRAINT gamme_nom IF NOT EXISTS FOR (g:Gamme) REQUIRE g.nom IS UNIQUE")

    def merge_gamme(self, nom):
        self.run("MERGE (:Gamme {nom: $nom})", nom=nom)

    def merge_classe(self, nom, attributs=None):
        if attributs is None:
            attributs = []
        self.run("MERGE (c:Classe {nom: $nom})", nom=nom)
        for attr in attributs:
            self.add_attribut_to_classe(classe=nom, attribut=attr["nom"], type_attr=attr.get("type"))

    def merge_enum(self, nom, valeurs):
        self.run("MERGE (e:Enum {nom:$nom})", nom=nom)
        for valeur in valeurs:
            self.run("""
            MERGE (e:Enum {nom:$enum})
            MERGE (v:ValeurEnum {nom:$valeur, key:$key})
            MERGE (e)-[:A_VALEUR_ENUM]->(v)
            """, enum=nom, valeur=valeur, key=f"{nom}.{valeur}")
    
    def link_attribut_to_enum(self, classe, attribut, enum):
        key = f"{classe}.{attribut}"
        self.run("""
        MATCH (a:Attribut {key:$key})
        MERGE (e:Enum {nom:$enum})
        MERGE (a)-[:EST_DE_TYPE]->(e)
        """, key=key, enum=enum)

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
        allowed = {"HERITE_DE", "ASSOCIE_A", "COMPOSE_DE", "AGREGE", "REFERENCE", "DECRIT", "TYPE_PAR", "A_VALEUR"}
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

# =================================================================
    # 1. Gamme de fabrication Ariane Coeur V0.1
    # =================================================================
    g1 = "Gamme de fabrication Ariane Coeur V0.1"
    builder.merge_gamme(g1)
    
    # --- Déclaration de toutes tes classes et attributs réels ---
    builder.merge_classe("ObjetPersistant", [{"nom": "dateCreation", "type": "P-Datetime"}, {"nom": "id", "type": "P-String"}, {"nom": "revision", "type": "P-Long"}])
    builder.merge_classe("ReferenceObjetRevision", [{"nom": "revision", "type": "P-Long Integer"}])
    builder.merge_classe("RessourceAbstraite", [{"nom": "dateDebutActivite", "type": "P-Datetime"}, {"nom": "dateFinActivite", "type": "P-Datetime"}, {"nom": "idExterne", "type": "P-Long"}])
    builder.merge_classe("RessourceAbstraiteNommee")
    builder.merge_classe("ElementADateAbstrait", [{"nom": "dateDebutActivite", "type": "P-Datetime"}, {"nom": "dateFinActivite", "type": "P-Datetime"}])
    builder.merge_classe("LibelleRessource", [{"nom": "libelle", "type": "P-String"}])
    builder.merge_classe("ImplantationAbstraite")
    
    # Bloc IFX (Installations Fixes)
    builder.merge_classe("TypeEtat", [{"nom": "code", "type": "P-String"}, {"nom": "mnemo", "type": "P-String"}])
    builder.merge_classe("RessourceInstallationFixe", [{"nom": "coordonneeX", "type": "P-Integer"}, {"nom": "coordonneeY", "type": "P-Integer"}, {"nom": "dateFinService", "type": "P-Datetime"}, {"nom": "libelleObstacle", "type": "P-String"}, {"nom": "longueur", "type": "P-Integer"}])
    builder.merge_classe("InstallationFixeVirtuelle")
    
    # Bloc Physique Complet
    builder.merge_classe("RessourcePhysique")
    builder.merge_classe("TypeAssociationRessourcePhysique", [{"nom": "code", "type": "P-String"}])
    builder.merge_classe("RessourcePhysiqueUnitaire", [{"nom": "dateFabrication", "type": "P-Datetime"}, {"nom": "identifiant", "type": "P-String"}])
    builder.merge_classe("RessourcePhysiqueMesurable", [{"nom": "dateDePoste", "type": "P-Datetime"}])
    builder.merge_classe("AssociationRessourcePhysique", [{"nom": "dateAssociation", "type": "P-Datetime"}])
    
    # Bloc Structurel & Caractéristiques
    builder.merge_classe("AssociationRessourceStructurelle", [{"nom": "dateAssociation", "type": "P-Datetime"}, {"nom": "quantite", "type": "P-Double"}])
    builder.merge_classe("CaractéristiqueElement")
    builder.merge_classe("CaracteristiqueSymbole")
    builder.merge_classe("LigneProduit", [{"nom": "code", "type": "P-String"}, {"nom": "contact", "type": "P-String"}, {"nom": "mnemo", "type": "P-String"}, {"nom": "responsable", "type": "P-String"}])
    builder.merge_classe("RessourceStructurelle", [{"nom": "mnemo", "type": "P-String"}])
    
    # Bloc Traçabilité / Métadonnées
    builder.merge_classe("CommentaireAbstrait")
    builder.merge_classe("ProvenanceObjet", [{"nom": "codeEntite", "type": "P-String"}, {"nom": "libelleEntite", "type": "P-String"}, {"nom": "codeProjet", "type": "P-String"}, {"nom": "codeService", "type": "P-String"}])
    builder.merge_classe("TypeProvenenance", [{"nom": "provenance", "type": "P-String"}])
    builder.merge_classe("Objectchecksum", [{"nom": "checksum", "type": "P-String"}])

    # =================================================================
    # MAPPAGE DES RELATIONS (HÉRITAGES & STRUCTURES DE L'IMAGE)
    # =================================================================
    
    # Flèches d'héritage (Blanches)
    builder.add_relation("RessourceAbstraite", "HERITE_DE", "ObjetPersistant")
    builder.add_relation("RessourceAbstraiteNommee", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("LibelleRessource", "HERITE_DE", "ElementADateAbstrait")
    
    # Héritages du bloc Physique
    builder.add_relation("RessourcePhysique", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("RessourcePhysiqueUnitaire", "HERITE_DE", "RessourcePhysique")
    builder.add_relation("RessourcePhysiqueMesurable", "HERITE_DE", "RessourcePhysique")
    
    # Héritages du bloc IFX & Structurel
    builder.add_relation("RessourceInstallationFixe", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("InstallationFixeVirtuelle", "HERITE_DE", "RessourceInstallationFixe")
    builder.add_relation("RessourceStructurelle", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("CaracteristiqueSymbole", "HERITE_DE", "CaractéristiqueElement")
    builder.add_relation("LigneProduit", "HERITE_DE", "CaractéristiqueElement")

    # Compositions & Liaisons (Losanges noirs et flèches de l'image)
    builder.add_relation("RessourceAbstraiteNommee", "COMPOSE_DE", "LibelleRessource", "libelles")
    builder.add_relation("ObjetPersistant", "PROVIENT_DE", "ProvenanceObjet")
    builder.add_relation("ProvenanceObjet", "A_POUR_TYPE", "TypeProvenenance")
    builder.add_relation("ObjetPersistant", "A_POUR_CHECKSUM", "Objectchecksum")
    builder.add_relation("ObjetPersistant", "A_POUR_REFERENCE", "ReferenceObjetRevision")
    
    # Connexions croisées (Liaisons inter-blocs)
    builder.add_relation("RessourceAbstraite", "A_POUR_CARACTERISTIQUE", "CaractéristiqueElement", "caracteristiques")
    builder.add_relation("RessourceAbstraite", "A_POUR_IMPLANTATION", "ImplantationAbstraite", "implantationFonctionnelle")
    builder.add_relation("ImplantationAbstraite", "SE_COMPOSE_DE", "ImplantationAbstraite", "implantations")
    
    # Liaisons des associations (Physiques, Structurelles et IFX)
    builder.add_relation("AssociationRessourceStructurelle", "CONCERNE", "RessourceStructurelle", "ressourceStructurelle")
    builder.add_relation("RessourceStructurelle", "LIE_A_LIGNE", "LigneProduit", "ligneParente")
    builder.add_relation("AssociationRessourcePhysique", "LIE_A_TYPE", "TypeAssociationRessourcePhysique", "typeAssociation")
    builder.add_relation("AssociationRessourcePhysique", "CONCERNE_PHYSIQUE", "RessourcePhysique", "ressourcePhysique")
    builder.add_relation("RessourceInstallationFixe", "A_POUR_ETAT", "TypeEtat", "typeEtat")

    # =================================================================
    # LIAISON SÉCURISÉE DE TOUTES LES CLASSES SANS EXCEPTION
    # =================================================================
    toutes_les_classes = [
        "ObjetPersistant", "ReferenceObjetRevision", "RessourceAbstraite", 
        "RessourceAbstraiteNommee", "ElementADateAbstrait", "LibelleRessource", 
        "ImplantationAbstraite", "TypeEtat", "RessourceInstallationFixe", 
        "InstallationFixeVirtuelle", "RessourcePhysique", "TypeAssociationRessourcePhysique", 
        "RessourcePhysiqueUnitaire", "RessourcePhysiqueMesurable", "AssociationRessourcePhysique", 
        "AssociationRessourceStructurelle", "CaractéristiqueElement", "CaracteristiqueSymbole", 
        "LigneProduit", "RessourceStructurelle", "CommentaireAbstrait", 
        "ProvenanceObjet", "TypeProvenenance", "Objectchecksum"
    ]
    
    for c in toutes_les_classes:
        builder.link_gamme_to_classe(g1, c)

    # =================================================================
    # 2. Gamme de fabrication RessourceInstallationFixe
    # =================================================================
    g2 = "Gamme de fabrication RessourceInstallationFixe"
    builder.merge_gamme(g2)
    builder.merge_classe("RessourceInstallationFixe", [
        {"nom": "coordonneeX", "type": "P-Integer"}, {"nom": "coordonneeY", "type": "P-Integer"},
        {"nom": "dateFinService", "type": "P-Datetime"}, {"nom": "libelleObstacle", "type": "P-String"},
        {"nom": "longueur", "type": "P-Integer"}
    ])
    builder.merge_classe("TypeInstallationFixe", [{"nom": "code", "type": "P-String"}, {"nom": "mnemo", "type": "P-String"}, {"nom": "indicLigVoi", "type": "EnumIndicateurLigneVoie"}])
    builder.merge_classe("RelationRessourceInstallationFixe")
    builder.merge_classe("RelationRessourceInstallationFixeOrdonnee", [{"nom": "rang", "type": "P-Integer"}])
    builder.merge_classe("RelationRessourceInstallationFixeDeleguee")
    builder.merge_classe("RelationRessourceInstallationFixeCommandee")
    builder.merge_classe("RelationRessourceInstallationFixeExtremite")
    builder.merge_classe("RelationRessourceInstallationFixeControlee")
    builder.merge_classe("TypeRelationRessourceInstallationFixe", [{"nom" : "code" , "type" : "P-String"}, {"nom" : "libelle", "type" : "P-String"}])
    builder.merge_classe("RelationExtremiteLiaison")
    builder.merge_classe("RelationInstallationFixeComposant")
    builder.merge_classe("RelationMiseEnOeuvre")
    builder.merge_classe("RelationResourceIFxAlimentationDisponible")
    builder.merge_classe("RelationResourceIFxAlimentationSecours")
    builder.merge_classe("RelationResourceFxAlimentationNormale")
    builder.merge_classe("ImplantationAbstraite")
    builder.merge_classe("ImplantationMultiPonctuelle")
    

    

    builder.add_relation("RessourceInstallationFixe", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("InstallationFixe", "HERITE_DE", "RessourceInstallationFixe")
    builder.add_relation("RessourceInstallationFixe", "TYPE_PAR", "TypeInstallationFixe", "typeInstallationFixe")
    builder.add_relation("RessourceInstallationFixe", "COMPOSE_DE", "RelationRessourceInstallationFixe", "relationsInstallationsFixes")
    builder.add_relation("RelationRessourceInstallationFixeOrdonnee", "HERITE_DE", "RelationRessourceInstallationFixe")

    builder.link_gamme_to_classe(g2, "RessourceInstallationFixe")
    builder.link_gamme_to_classe(g2, "TypeInstallationFixe")

    # =================================================================
    # 3. Gamme de fabrication : Passage à Niveau
    # =================================================================
    g3 = "Gamme de fabrication : Passage à Niveau"
    builder.merge_gamme(g3)
    builder.merge_classe("PassageANiveau", [
        {"nom": "codeLigneDesignation", "type": "P-String"}, {"nom": "delaiReelFermetureCroissant", "type": "P-Float"},
        {"nom": "delaiReelFermetureDecroissant", "type": "P-Float"}, {"nom": "delaiTheoriqueFermeture", "type": "P-Float"},
        {"nom": "dureemaxFermeture", "type": "P-Float"}, {"nom": "preoccupant", "type": "P-Boolean"},
        {"nom": "circulationConception", "type": "P-Integer"}, {"nom": "indicDifficulteFranchissement", "type": "EnumIndicateur"},
        {"nom": "indicPlaqueGAMEC", "type": "EnumIndicateur"}, {"nom": "indicTelephone", "type": "EnumIndicateur"},
        {"nom": "indicZoneHumide", "type": "EnumIndicateur"}, {"nom": "largeur", "type": "P-Integer"},
        {"nom": "longueurTraversee", "type": "P-Integer"}, {"nom": "momentProduitTrainCirculationConception", "type": "P-Integer"},
        {"nom": "visibiliteCroissanteEnMetre", "type": "P-Integer"}, {"nom": "visibiliteDeCroissanteEnMetre", "type": "P-Integer"},
        {"nom": "visibiliteCroissanteEnSeconde", "type": "P-Integer"}, {"nom": "visibiliteDeCroissanteEnSeconde", "type": "P-Integer"}
    ])
    builder.merge_classe("ProfilEnLongRoutier", [{"nom": "margeGardeAuSol", "type": "P-Double"}, {"nom": "margePorteFaux", "type": "P-Double"}])
    builder.merge_classe("ElementProfilRoutier", [{"nom": "abscisse", "type": "P-Double"}, {"nom": "altitude", "type": "P-Double"}, {"nom": "abscisseSurRail", "type": "EnumIndicateur"}])

    builder.add_relation("PassageANiveau", "HERITE_DE", "RessourceInstallationFixe")
    builder.add_relation("ProfilEnLongRoutier", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("ElementProfilRoutier", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("ProfilEnLongRoutier", "COMPOSE_DE", "ElementProfilRoutier", "elementsProfilsRoutiers")

    builder.link_gamme_to_classe(g3, "PassageANiveau")
    builder.link_gamme_to_classe(g3, "ProfilEnLongRoutier")
    builder.link_gamme_to_classe(g3, "ElementProfilRoutier")

    # =================================================================
    # 4. Gamme de fabrication : Point d’information ETCS
    # =================================================================
    g4 = "Gamme de fabrication : Point d’information ETCS"
    builder.merge_gamme(g4)
    builder.merge_classe("PointInformationETCS", [
        {"nom": "chaine", "type": "EnumIndicateur"},
        {"nom": "codeRegion", "type": "P-Integer"},
        {"nom": "numero", "type": "P-Integer"}
    ])
    builder.merge_classe("PointInformation")
    builder.merge_classe("Eurobalise", [{"nom": "dupliquee", "type": "EnumIndicateur"}])

    builder.add_relation("PointInformation", "HERITE_DE", "InstallationFixe")
    builder.add_relation("PointInformationETCS", "HERITE_DE", "PointInformation")
    builder.add_relation("Eurobalise", "HERITE_DE", "InstallationFixe")

    builder.link_gamme_to_classe(g4, "PointInformationETCS")
    builder.link_gamme_to_classe(g4, "Eurobalise")

    # =================================================================
    # 5. Gamme de fabrication : balise KVB V6
    # =================================================================
    g5 = "Gamme de fabrication : balise KVB V6"
    builder.merge_gamme(g5)
    builder.merge_classe("PointInformationKVB")
    builder.merge_classe("BaliseKVB")
    builder.merge_classe("MessageKVB")
    builder.merge_classe("ChampInformationKVB", [{"nom": "observation", "type": "P-String"}, {"nom": "sens", "type": "EnumSensDeLecture"}])
    builder.merge_classe("ChampInformationKVBPointBut", [{"nom": "declivite", "type": "P-Double"}, {"nom": "distanceBut", "type": "P-Integer"}, {"nom": "indSortieVS", "type": "EnumIndicateur"}])
    builder.merge_classe("PointBut", [{"nom": "distance", "type": "P-Integer"}, {"nom": "positionnement", "type": "EnumPositionPointBut"}])
    builder.merge_classe("VitesseBut", [{"nom": "vitesseBut", "type": "P-Integer"}])
    builder.merge_classe("CatégorieKVB")

    builder.add_relation("PointInformationKVB", "HERITE_DE", "PointInformation")
    builder.add_relation("BaliseKVB", "HERITE_DE", "InstallationFixe")
    builder.add_relation("MessageKVB", "HERITE_DE", "Message")
    builder.add_relation("ChampInformationKVB", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("ChampInformationKVBPointBut", "HERITE_DE", "ChampInformationKVB")

    for c in ["PointInformationKVB", "BaliseKVB", "ChampInformationKVB", "ChampInformationKVBPointBut", "PointBut", "VitesseBut"]:
        builder.link_gamme_to_classe(g5, c)

    # =================================================================
    # 6. Gamme de fabrication : Transit et Groupement de Zone
    # =================================================================
    g6 = "Gamme de fabrication : Transit et Groupement de Zone"
    builder.merge_gamme(g6)
    builder.merge_classe("GroupementDeZone")
    builder.merge_classe("ZoneDeDetection")
    builder.merge_classe("Transit", [{"nom": "parite", "type": "P-String"}])
    builder.merge_classe("ContrainteTransit")
    builder.merge_classe("Itinéraire")

    builder.add_relation("GroupementDeZone", "HERITE_DE", "RessourceInstallationFixe")
    builder.add_relation("Transit", "HERITE_DE", "RessourceInstallationFixe")
    builder.add_relation("ContrainteTransit", "HERITE_DE", "ContrainteItineraire")

    for c in ["GroupementDeZone", "ZoneDeDetection", "Transit", "ContrainteTransit"]:
        builder.link_gamme_to_classe(g6, c)

    # =================================================================
    # 7. Gamme de fabrication : topologie
    # =================================================================
    g7 = "Gamme de fabrication : topologie"
    builder.merge_gamme(g7)
    builder.merge_classe("RessourceParcoursTopologique")
    builder.merge_classe("RessourceParcoursTopologiqueADate")
    builder.merge_classe("RessourceConnexionOrientee")
    builder.merge_classe("MouvementPossible", [{"nom": "mouvementPossible", "type": "EnumMouvement"}])
    builder.merge_classe("ElementTopologiqueLinéaire")
    builder.merge_classe("ExtrémitéRéseau")
    builder.merge_classe("TypeExtrémitéRéseau", [{"nom": "mnemo", "type": "P-String"}])
    builder.merge_classe("ElementTopologiqueLineaireLigne")
    builder.merge_classe("Ligne", [
        {"nom": "code", "type": "P-String"}, {"nom": "dateAttribution", "type": "P-Datetime"},
        {"nom": "libelle", "type": "P-String"}, {"nom": "reservee", "type": "P-Boolean"}
    ])
    builder.merge_classe("TypeLigne", [{"nom": "code", "type": "P-String"}, {"nom": "mnemo", "type": "P-String"}])
    builder.merge_classe("TroncCommun")
    builder.merge_classe("ElementTopologiqueLineaireVoie")
    builder.merge_classe("Voie", [{"nom": "nom", "type": "P-String"}])
    builder.merge_classe("TypeDeVoie", [{"nom": "mnemonique", "type": "P-String"}])
    builder.merge_classe("VoieDeLigne")
    builder.merge_classe("VoieDeSaf", [{"nom": "nom", "type": "P-String"}])
    builder.merge_classe("ExtremitéVoie")

    builder.add_relation("RessourceParcoursTopologique", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("RessourceParcoursTopologiqueADate", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("MouvementPossible", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("ElementTopologiqueOriente", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("ElementTopologiqueLinéaire", "HERITE_DE", "ElementTopologiqueOriente")
    builder.add_relation("ExtrémitéRéseau", "HERITE_DE", "ElementTopologiquePonctuel")
    builder.add_relation("TypeExtrémitéRéseau", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("ElementTopologiqueLineaireLigne", "HERITE_DE", "ElementTopologiqueLinéaire")
    builder.add_relation("Ligne", "HERITE_DE", "RessourceParcoursTopologique")
    builder.add_relation("TypeLigne", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("ElementTopologiqueLineaireVoie", "HERITE_DE", "ElementTopologiqueLinéaire")
    builder.add_relation("Voie", "HERITE_DE", "RessourceParcoursTopologique")
    builder.add_relation("VoieDeLigne", "HERITE_DE", "Voie")
    builder.add_relation("VoieDeSaf", "HERITE_DE", "Voie")

    for c in ["RessourceParcoursTopologique", "RessourceConnexionOrientee", "MouvementPossible", "Ligne", "Voie", "VoieDeLigne", "VoieDeSaf"]:
        builder.link_gamme_to_classe(g7, c)

    # =================================================================
    # 8. Gamme de fabrication : Système de repérage
    # =================================================================
    g8 = "Gamme de fabrication : Système de repérage"
    builder.merge_gamme(g8)
    builder.merge_classe("SystemeReperage")
    builder.merge_classe("SystemeReperagePk", [{"nom": "pkDebut", "type": "P-Long"}, {"nom": "pkFin", "type": "P-Long"}])
    builder.merge_classe("SystemeReperageVoie")
    builder.merge_classe("SystemeReperageLigne", [{"nom": "rang", "type": "P-Integer"}])
    builder.merge_classe("SystemeReperageAdministratif")
    builder.merge_classe("SystemeReperageCurviligne", [{"nom": "pk_debut", "type": "P-Long"}, {"nom": "pk_fin", "type": "P-Long"}])
    builder.merge_classe("SystemeReperageGeodesique")
    builder.merge_classe("AnomalieSR", [{"nom": "rkPrecedent", "type": "P-Integer"}, {"nom": "typeAnomalie", "type": "EnumAnomalie"}, {"nom": "valeur", "type": "P-Integer"}])
    builder.merge_classe("RepereDeCalibragePkGeo")
    builder.merge_classe("PointDeCalibragePK", [{"nom": "exclu", "type": "P-Boolean"}])
    builder.merge_classe("PointDeCalibrageIFX")

    builder.add_relation("SystemeReperage", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("SystemeReperagePk", "HERITE_DE", "SystemeReperage")
    builder.add_relation("SystemeReperageVoie", "HERITE_DE", "SystemeReperagePk")
    builder.add_relation("SystemeReperageLigne", "HERITE_DE", "SystemeReperagePk")
    builder.add_relation("SystemeReperageAdministratif", "HERITE_DE", "SystemeReperagePk")
    builder.add_relation("AnomalieSR", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("RepereDeCalibragePkGeo", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("PointDeCalibragePK", "HERITE_DE", "ObjetPersistant")
    builder.add_relation("PointDeCalibrageIFX", "HERITE_DE", "PointDeCalibragePK")

    for c in ["SystemeReperage", "SystemeReperagePk", "AnomalieSR", "RepereDeCalibragePkGeo", "PointDeCalibragePK"]:
        builder.link_gamme_to_classe(g8, c)

    # =================================================================
    # 9. Gamme de fabrication : Secteur d’Activité Ferroviaire
    # =================================================================
    g9 = "Gamme de fabrication : Secteur d’Activité Ferroviaire"
    builder.merge_gamme(g9)
    builder.merge_classe("Saf", [
        {"nom": "categorieCommerciale", "type": "P-String"},
        {"nom": "commentaireAccessibilite", "type": "P-String"},
        {"nom": "commentaireOrientation", "type": "P-String"},
        {"nom": "commentaireOuverture", "type": "P-String"}
    ])
    builder.merge_classe("TypeSafADate")
    builder.merge_classe("TypeSaf", [{"nom": "mnemo", "type": "P-String"}])
    builder.merge_classe("RelationSafPere")
    builder.merge_classe("RelationIdentifiantSaf")
    builder.merge_classe("RelationIdentifiantSafSaf")
    builder.merge_classe("RelationIdentifiantSafGare")

    builder.add_relation("Saf", "HERITE_DE", "ElementTopologiqueOriente")
    builder.add_relation("TypeSafADate", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("TypeSaf", "HERITE_DE", "RessourceAbstraiteNommee")
    builder.add_relation("RelationSafPere", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("RelationIdentifiantSaf", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("RelationIdentifiantSafSaf", "HERITE_DE", "RelationIdentifiantSaf")
    builder.add_relation("RelationIdentifiantSafGare", "HERITE_DE", "RelationIdentifiantSaf")

    builder.link_gamme_to_classe(g9, "Saf")

    # =================================================================
    # 10. Gamme de fabrication : Localisation et Implantation
    # =================================================================
    g10 = "Gamme de fabrication : Localisation et Implantation"
    builder.merge_gamme(g10)
    builder.merge_classe("LocalisationSR")
    builder.merge_classe("LocalisationPk", [
        {"nom": "indicCalcule", "type": "P-Boolean"}, {"nom": "indicFiable", "type": "P-Boolean"},
        {"nom": "indicPkFictif", "type": "P-Boolean"}, {"nom": "nomVoie", "type": "P-String"},
        {"nom": "origineLocalisation", "type": "EnumOrigineLocalisation"},
        {"nom": "pk", "type": "P-Long"}, {"nom": "positionLocalisation", "type": "P-String"},
        {"nom": "sensLecture", "type": "EnumSensLecture"}
    ])
    builder.merge_classe("LocationCartographique", [{"nom": "coordonneeX", "type": "P-Double"}, {"nom": "coordonneeY", "type": "P-Double"}, {"nom": "coordonneeZ", "type": "P-Double"}])
    builder.merge_classe("LocalisationGeometrique", [{"nom": "coordonneeX", "type": "P-Double"}, {"nom": "coordonneeY", "type": "P-Double"}, {"nom": "coordonneeZ", "type": "P-Double"}])
    builder.merge_classe("RelationImplantationInstallationFixe", [{"nom": "rang", "type": "P-Integer"}])
    builder.merge_classe("ImplantationGeometrique")
    builder.merge_classe("ImplantationLineaireSRPK")
    builder.merge_classe("ImplantationPonctuelleSRPK")
    builder.merge_classe("ImplantationCartographique")
    builder.merge_classe("ImplantationPonctuelle")
    builder.merge_classe("ImplantationMultiPonctuelle")
    builder.merge_classe("ImplantationTopologiqueLineaire")
    builder.merge_classe("ImplantationRessourceParcoursInfrastructure")
    builder.merge_classe("ImplantationLineaireRessourceParcoursInfrastructure")

    builder.add_relation("LocalisationSR", "HERITE_DE", "ElementADateAbstrait")
    builder.add_relation("LocalisationPk", "HERITE_DE", "LocalisationSR")
    builder.add_relation("ImplantationAbstraite", "HERITE_DE", "RessourceAbstraite")
    builder.add_relation("ImplantationGeometrique", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationLineaireSRPK", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationPonctuelleSRPK", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationCartographique", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationPonctuelle", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationMultiPonctuelle", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationTopologiqueLineaire", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationRessourceParcoursInfrastructure", "HERITE_DE", "ImplantationAbstraite")
    builder.add_relation("ImplantationLineaireRessourceParcoursInfrastructure", "HERITE_DE", "ImplantationAbstraite")

    for c in ["LocalisationSR", "LocalisationPk", "LocationCartographique", "LocalisationGeometrique", "ImplantationAbstraite"]:
        builder.link_gamme_to_classe(g10, c)

    # =================================================================
    # 11. Gamme de fabrication : Représentation géométrique
    # =================================================================
    g11 = "Gamme de fabrication : Représentation géométrique d’un élément topologique"
    builder.merge_gamme(g11)
    builder.merge_classe("RessourceGeometrieAbstraite")
    builder.merge_classe("GinstanceGeometrie")
    builder.merge_classe("GinstanceGeometrieMultimedia", [{"nom": "contenu", "type": "P-Blob"}, {"nom": "type", "type": "P-String"}])
    builder.merge_classe("GPR")
    builder.merge_classe("Gvisuel")
    builder.merge_classe("GTIV")
    builder.merge_classe("GTIL")
    builder.merge_classe("InstanceGeographique")
    builder.merge_classe("InstanceSchematique")
    builder.merge_classe("GelementOgc")
    builder.merge_classe("Geometry")
    builder.merge_classe("Point", [{"nom": "x", "type": "P-Double"}, {"nom": "y", "type": "P-Double"}, {"nom": "z", "type": "P-Double"}])
    builder.merge_classe("Curve")
    builder.merge_classe("Surface")
    builder.merge_classe("LineString")
    builder.merge_classe("Polygon")

    builder.add_relation("RessourceGeometrieAbstraite", "HERITE_DE", "ObjetPersistant")
    builder.add_relation("GinstanceGeometrie", "HERITE_DE", "RessourceGeometrieAbstraite")
    builder.add_relation("GinstanceGeometrieMultimedia", "HERITE_DE", "RessourceGeometrieAbstraite")
    builder.add_relation("GPR", "HERITE_DE", "GinstanceGeometrie")
    builder.add_relation("Gvisuel", "HERITE_DE", "GinstanceGeometrie")
    builder.add_relation("GTIV", "HERITE_DE", "GinstanceGeometrie")
    builder.add_relation("GTIL", "HERITE_DE", "GinstanceGeometrie")
    builder.add_relation("Geometry", "HERITE_DE", "ObjetPersistant")
    builder.add_relation("Point", "HERITE_DE", "Geometry")
    builder.add_relation("Curve", "HERITE_DE", "Geometry")
    builder.add_relation("Surface", "HERITE_DE", "Geometry")
    builder.add_relation("LineString", "HERITE_DE", "Curve")
    builder.add_relation("Polygon", "HERITE_DE", "Surface")

    for c in ["RessourceGeometrieAbstraite", "GinstanceGeometrie", "GTIV", "GTIL", "Geometry"]:
        builder.link_gamme_to_classe(g11, c)

    # =================================================================
    # 12. Gamme de fabrication : Repère de calibrage
    # =================================================================
    g12 = "Gamme de fabrication : Repère de calibrage"
    builder.merge_gamme(g12)
    for c in ["RepereDeCalibragePkGeo", "PointDeCalibragePK", "PointDeCalibrageIFX"]:
        builder.link_gamme_to_classe(g12, c)

    # =================================================================
    # TOUTES LES ÉNUMÉRATIONS MÉTIERS EXPLICITES
    # =================================================================
    builder.merge_enum("EnumIndicateur", ["O", "N", "NR"])
    builder.merge_enum("EnumSensHabillage", ["Pair", "Impair", "LesDeux"])
    builder.merge_enum("EnumOrigineLocalisation", ["IF", "IF_PR", "PR", "NA"])
    builder.merge_enum("EnumPositionLocalisation", ["NA"])
    builder.merge_enum("EnumSensLecture", ["B"])
    builder.merge_enum("EnumSensDeLecture", ["A", "D", "C"])
    builder.merge_enum("EnumPositionPointBut", ["EST_POSITIONNE_SUR", "EST_POSITIONNE_AMONT", "EST_POSITIONNE_AVAL"])
    builder.merge_enum("EnumMouvement", ["B vers A", "A vers B", "les deux", "aucun"])
    builder.merge_enum("EnumAnomalie", ["V", "S", "A", "ordonnancement"])
    builder.merge_enum("enumPositionOT", ["Gauche", "Droite", "Dessus", "Dessous"])

    # Liaisons attributs -> Énumérations métiers
    builder.link_attribut_to_enum("PassageANiveau", "indicDifficulteFranchissement", "EnumIndicateur")
    builder.link_attribut_to_enum("PassageANiveau", "indicPlaqueGAMEC", "EnumIndicateur")
    builder.link_attribut_to_enum("PassageANiveau", "indicTelephone", "EnumIndicateur")
    builder.link_attribut_to_enum("PassageANiveau", "indicZoneHumide", "EnumIndicateur")
    builder.link_attribut_to_enum("ElementProfilRoutier", "abscisseSurRail", "EnumIndicateur")
    builder.link_attribut_to_enum("PointInformationETCS", "chaine", "EnumIndicateur")
    builder.link_attribut_to_enum("Eurobalise", "dupliquee", "EnumIndicateur")
    builder.link_attribut_to_enum("ChampInformationKVB", "sens", "EnumSensDeLecture")
    builder.link_attribut_to_enum("ChampInformationKVBPointBut", "indSortieVS", "EnumIndicateur")
    builder.link_attribut_to_enum("PointBut", "positionnement", "EnumPositionPointBut")
    builder.link_attribut_to_enum("MouvementPossible", "mouvementPossible", "EnumMouvement")
    builder.link_attribut_to_enum("AnomalieSR", "typeAnomalie", "EnumAnomalie")
    builder.link_attribut_to_enum("LocalisationPk", "origineLocalisation", "EnumOrigineLocalisation")
    builder.link_attribut_to_enum("LocalisationPk", "sensLecture", "EnumSensLecture")

    builder.close()
    print("Félicitations ! L'intégralité exacte des 12 gammes de fabrication est injectée.")