"""Contrôles locaux métier : aucune validation sémantique implicite, aucun appel LLM."""

from copy import deepcopy
import re
import unicodedata

VERSION_VALIDATION = 4
CATEGORIES = {
    "EQUIPEMENT", "OBJET_FERROVIAIRE", "TYPE_OBJET", "ACTEUR", "DOCUMENT",
    "PROCEDURE", "LOCALISATION", "DATE", "VALEUR", "CARACTERISTIQUE",
    "SYSTEME", "INCONNU",
}


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", str(texte or "").replace("œ", "oe").replace("Œ", "OE"))
    return " ".join(re.findall(r"[a-z0-9]+", "".join(
        c for c in texte if not unicodedata.combining(c)
    ).lower()))


INDICES_RELATIONS = {
    "A_POUR_TECHNOLOGIE": ("technologie", "type de poste", "mode de fonctionnement"),
    "COMMANDE": ("commande", "commandee", "commander", "manoeuvre"),
    "EST_COMMANDE_PAR": ("commande par", "commandee par"),
    "EST_UN": ("est un", "est une", "sont des", "type de", "categorie de"),
    "COMPOSE_DE": ("compose de", "composee de", "comprend", "constitue de", "constituee de", "comprendre"),
    "FAIT_PARTIE_DE": ("fait partie", "compose de", "comprend", "constitue de"),
    "LOCALISE_SUR": ("localise", "localisee", "situe", "situee", "pk", "localisation"),
    "DECRIT_PAR": ("decrit", "documente", "repris sur", "figure sur", "plan technique", "source"),
    "GERE_PAR": ("gere par", "geree par", "gestion par"),
    "A_POUR_ORIGINE": ("origine", "commence", "debut"),
    "A_POUR_DESTINATION": ("destination", "termine", "fin"),
    "CONCERNE": ("concerne", "concernant"),
    "DEPEND_DE": ("depend de", "sous la dependance"),
    "EMPRUNTE": ("emprunte", "empruntee", "empruntes"),
    "IMPACTE": ("impacte", "impact sur", "a un impact"),
    "NECESSITE": ("necessite", "obligatoire", "doit", "devra"),
    "PROTEGE_PAR": ("protege par", "protegee par"),
    "RATTACHE_A": ("rattache a", "rattachee a", "rattachement"),
    "REGLEMENTE_PAR": ("reglemente par", "consigne", "texte de reference"),
    "TRANSMET_A": ("transmet", "envoye", "emise par", "emises par", "recoit les informations"),
    "UTILISE": ("utilise", "utilisee", "utiliser", "usage de"),
    "A_POUR_CARACTERISTIQUE": ("hauteur", "longueur", "largeur", "nombre", "valeur", "type", "renseigner", "eclairage", "accessible", "indication"),
    "DEBUTE_A": ("date de debut", "dda"),
    "SE_TERMINE_A": ("date de fin", "dfa"),
    "DECLENCHE": ("declenche", "a partir de cette date"),
    "TRANSMET": ("transmet", "envoye", "envoi"),
    "DECRIT": ("decrit", "description", "document", "fiche"),
    "PROVIENT_DE": ("source", "provient", "issu"),
    "MIS_EN_PLACE_PAR": ("mis en place par", "mettre en place par"),
}
RELATIONS_AUTORISEES = set(INDICES_RELATIONS)
# Contraintes négatives : INCONNU reste à revoir, jamais validé par défaut.
NON_PHYSIQUES = {"DOCUMENT", "PROCEDURE", "DATE", "VALEUR", "CARACTERISTIQUE"}


def categorie_concept(concept):
    if concept.get("conflit_categories"):
        return "INCONNU"
    declared = concept.get("categorie")
    if declared in CATEGORIES and declared != "INCONNU":
        return declared
    nom = normaliser(concept.get("nom"))
    if re.match(r"^(date\b|dda$|dfa$)", nom):
        return "DATE"
    if re.match(r"^(plan technique\b|fiche\b|fichier\b|document\b|renseignement technique\b|schema de signalisation\b)", nom):
        return "DOCUMENT"
    if re.match(r"^(hauteur\b|longueur\b|largeur\b|nombre\b|type de couverture\b|type de revetement\b|libelle$)", nom):
        return "CARACTERISTIQUE"
    if re.match(r"^(pk\b|point kilometrique\b|repere kilometrique\b|localisation$)", nom):
        return "LOCALISATION"
    return "INCONNU"


def _changer(relation, source, predicat, cible, raison):
    relation.setdefault("corrections", []).append({
        "avant": {k: relation[k] for k in ("source", "type", "cible")},
        "raison": raison,
    })
    relation.update(source=source, type=predicat, cible=cible)


def normaliser_commande(relation, concepts):
    r = deepcopy(relation)
    if r.get("type") != "COMMANDE":
        return r
    preuve = r.get("preuve", {})
    if not isinstance(preuve, dict):
        return r
    texte = normaliser(preuve.get("citation"))
    match = re.search(r"\bcommandee?s? par\b", texte)
    if not match:
        return r
    def present(ident, fragment):
        concept = concepts.get(ident, {})
        noms = [concept.get("nom", "")] + concept.get("aliases", [])
        return any(n and re.search(r"\b" + re.escape(n) + r"s?\b", fragment)
                   for n in map(normaliser, noms))
    avant, apres = texte[:match.start()], texte[match.end():]
    s, c = r["source"], r["cible"]
    if present(s, avant) and present(c, apres):
        _changer(r, s, "EST_COMMANDE_PAR", c, "Voix passive, extrémités confirmées dans la citation.")
    elif present(c, avant) and present(s, apres):
        _changer(r, c, "EST_COMMANDE_PAR", s, "Voix passive : sujet commandé avant le verbe, contrôleur après.")
    return r


def corriger_relation(relation):
    """Décisions limitées aux cas relus et à leur preuve, pas aux seuls noms."""
    r = deepcopy(relation)
    s, t, c = r["source"], r["type"], r["cible"]
    p = r.get("preuve", {})
    citation = normaliser(p.get("citation", "")) if isinstance(p, dict) else ""
    doc = p.get("document", "") if isinstance(p, dict) else ""
    if t == "EST_UN":
        inverse = (
            (doc == "Ligne.txt" and s == "point_kilometrique" and c == "repere_kilometrique"
             and "le rk est un pk particulier" in citation)
            or (doc == "NoeudDeVoie.txt" and s in {"n_ud_de_ligne", "noeud_de_ligne"}
                and c in {"n_ud_pont", "n_ud_y", "n_ud_x", "n_ud_j", "n_ud_frontiere", "n_ud_intermediaire",
                          "noeud_pont", "noeud_y", "noeud_x", "noeud_j", "noeud_frontiere", "noeud_intermediaire"}
                and "le noeud" in citation)
            or (doc == "Post.txt" and s == "poste" and c.startswith(("poste_de_vp_", "poste_de_vs_"))
                and "poste de" in citation)
            or (doc == "Post.txt" and s == "poste" and c == "poste_divers"
                and "poste divers de moins de 10 leviers" in citation)
        )
        if inverse:
            _changer(r, c, t, s, "Typologie relue : le type spécialisé est la source.")
    if t == "COMPOSE_DE" and doc == "Quai.txt" and s == "quai" and c in {
        "longueur_totale", "longueur_utile", "hauteur_du_quai", "type_de_couverture",
        "type_de_revetement_du_sol", "dfa", "dda", "largeur_du_quai",
        "indication_quai_de_service", "eclairage", "nombre_d_ascenseurs",
        "nombre_d_escaliers_mecaniques", "nombre_de_rampes", "nombre_de_traversees",
        "type_de_traversee", "accessible_aux_personnes_a_mobilite_reduite",
    }:
        _changer(r, s, "A_POUR_CARACTERISTIQUE", c, "La fiche décrit un champ du quai, pas un composant.")
    if t == "LOCALISE_SUR" and doc == "Ligne.txt" and c == "fermeture_temporaire":
        if s == "date_de_debut_de_fermeture" and "date de debut" in citation:
            _changer(r, c, "DEBUTE_A", s, "Date de début de la fermeture, pas localisation.")
        elif s == "date_de_fin_de_fermeture" and "date de fin" in citation:
            _changer(r, c, "SE_TERMINE_A", s, "Date de fin de la fermeture, pas localisation.")
    if (s, t, c, doc) == ("quai", "LOCALISE_SUR", "plan_technique", "Quai.txt") and "plan technique" in citation:
        _changer(r, s, "DECRIT_PAR", c, "Le plan technique est une source documentaire.")
    return r


def controler_relation(relation, concepts, passage=None):
    r = normaliser_commande(corriger_relation(relation), concepts)
    raisons, avertissements = [], []
    s, t, c = r["source"], r["type"], r["cible"]
    preuve = r.get("preuve", {})
    citation = normaliser(preuve.get("citation", "")) if isinstance(preuve, dict) else ""
    if s not in concepts or c not in concepts:
        raisons.append("concept source ou cible absent")
    if s == c:
        raisons.append("auto-relation interdite après consolidation")
    if t not in RELATIONS_AUTORISEES:
        raisons.append("type de relation non autorisé")
    if len(citation) < 15 or (passage is not None and f" {citation} " not in f" {normaliser(passage)} "):
        raisons.append("citation absente du passage")
    if passage is None:
        avertissements.append("preuve documentaire à recontrôler sur la fiche")
    cs, cc = categorie_concept(concepts.get(s, {})), categorie_concept(concepts.get(c, {}))
    if t in {"COMMANDE", "EST_COMMANDE_PAR"} and (cs in NON_PHYSIQUES or cc in NON_PHYSIQUES):
        raisons.append("commande incompatible avec une date, un document ou une caractéristique")
    if t == "LOCALISE_SUR" and (cs in {"DATE", "DOCUMENT"} or cc in {"DATE", "DOCUMENT"}):
        raisons.append("localisation incompatible avec une date ou un document")
    if t == "COMPOSE_DE" and cc in {"DATE", "VALEUR", "CARACTERISTIQUE"}:
        avertissements.append("composition suspecte : la cible est une propriété")
    if t == "DECRIT_PAR" and cc not in {"DOCUMENT", "PROCEDURE", "INCONNU"}:
        avertissements.append("la cible de DECRIT_PAR devrait être une source documentaire")
    indices = INDICES_RELATIONS.get(t, ())
    if indices and not any(i in citation for i in indices):
        avertissements.append("prédicat non confirmé textuellement")
    if t in {"COMMANDE", "EST_COMMANDE_PAR"} and not any(i in citation for i in ("command", "manoeuv")):
        raisons.append("citation sans action de commande")
    # Rejets métier documentés par l'audit ; ne pas inventer de relation de remplacement.
    doc = preuve.get("document", "") if isinstance(preuve, dict) else ""
    incompatibles = {
        ("CantonEmprunte.txt", "cantonnement", "EST_UN", "itineraire"): "un dispositif d espacement des trains",
        ("HabillageCourantMaxCatenaire.txt", "selecteur_de_puissance", "EST_UN", "poste_de_conduite"): "present dans le poste de conduite",
        ("PassageANiveau.txt", "passage_a_niveau", "EST_UN", "obstacle"): "est un croisement des voies ferrees",
        ("Saf.txt", "plan_technique", "EST_UN", "localisation"): "le plan technique est la source prioritaire",
        ("ZEP.txt", "sam", "EST_UN", "installation_fixe"): "dispositifs de securite provisoires",
        ("ZEP.txt", "jalon_d_arret", "EST_UN", "installation_fixe"): "dispositifs de securite provisoires",
        ("ZEP.txt", "zone_elementaire_de_protection", "EST_UN", "signal"): "choix du type d extremite",
        ("ZEP.txt", "zone_elementaire_de_protection", "EST_UN", "installation_exterieure"): "choix du type d extremite",
        ("Acces.txt", "acces", "COMPOSE_DE", "ligne"): "permettant a partir de l infrastructure routiere",
        ("Ligne.txt", "ligne", "COMPOSE_DE", "voie"): "dissocier la notion de ligne et la notion de voie",
        ("PassageANiveau.txt", "fiche_d_echange", "COMPOSE_DE", "passage_a_niveau"): "ce document a pour objet d eviter les suppressions",
    }
    indice_rejet = incompatibles.get((doc, s, t, c))
    if indice_rejet and indice_rejet in citation:
        raisons.append("relation incompatible avec le sens du passage relu (audit métier)")
    if any(x in citation for x in ("ne doit pas", "ne sont pas", "n est pas", "muni ou non", "peut etre", "ce peut etre")):
        avertissements.append("négation ou modalité : ne pas interpréter comme un fait universel")
    if "INCONNU" in {cs, cc}:
        avertissements.append("catégorie source ou cible à préciser")
    preuve_exacte = bool(
        len(citation) >= 15
        and passage is not None
        and f" {citation} " in f" {normaliser(passage)} "
    )
    concepts_identifies = s in concepts and c in concepts
    predicat_confirme = not indices or any(i in citation for i in indices)
    # Un contrôle lexical ne démontre pas le sens d'un triplet.
    # Le classement reste tolérant : sans confirmation, on conserve PROBABLE.
    direction_confirmee = False
    if t == "EST_COMMANDE_PAR":
        match = re.search(r"\bcommandee?s? par\b", citation)
        if match:
            def mention(ident, fragment):
                concept = concepts.get(ident, {})
                noms = [concept.get("nom", "")] + concept.get("aliases", [])
                return any(n and re.search(r"\b" + re.escape(n) + r"s?\b", fragment)
                           for n in map(normaliser, noms))
            direction_confirmee = bool(
                mention(s, citation[:match.start()])
                and mention(c, citation[match.end():])
            )
    if not direction_confirmee:
        avertissements.append("sens de la relation non confirmé automatiquement")
    modalite_detectee = any(x in citation for x in (
        "ne doit pas", "ne sont pas", "n est pas", "muni ou non",
        "peut etre", "ce peut etre", "dans la plupart des cas",
    ))
    condition_complete = not modalite_detectee or bool(
        r.get("condition") or r.get("exception")
    )
    criteres = {
        "preuve_exacte": preuve_exacte,
        "concepts_identifies": concepts_identifies,
        "predicat_confirme": predicat_confirme,
        "direction_confirmee": direction_confirmee,
        "condition_complete": condition_complete,
    }
    score = (
        30 * int(preuve_exacte)
        + 20 * int(concepts_identifies)
        + 20 * int(predicat_confirme)
        + 15 * int(direction_confirmee)
        + 15 * int(condition_complete)
    )
    if raisons:
        statut = "REJETE"
    elif (preuve_exacte and predicat_confirme and direction_confirmee
          and condition_complete and "INCONNU" not in {cs, cc} and score >= 85):
        statut = "VALIDE"
    else:
        statut = "PROBABLE"
    r.update(
        statut=statut,
        niveau_validation="DOCUMENTAIRE",
        validation_experte=False,
        score_confiance=round(score / 100, 2),
        criteres=criteres,
        version_validation=VERSION_VALIDATION,
        motifs_rejet=raisons,
        avertissements=sorted(set(avertissements)),
    )
    return r


def verifier_import(definition):
    """Garde impérative avant toute écriture, y compris via le builder direct."""
    concepts = definition.get("concepts", [])
    ids = {c["id"] for c in concepts}
    if len(ids) != len(concepts):
        raise ValueError("Identifiants de concepts non uniques")
    if any(c.get("statut") not in {"VALIDE", "PROBABLE"} for c in concepts):
        raise ValueError("Import refusé : concept ni VALIDE ni PROBABLE")
    for r in definition.get("relations", []):
        if r.get("statut") not in {"VALIDE", "PROBABLE"} or r.get("motifs_rejet"):
            raise ValueError("Import refusé : relation ni VALIDE ni PROBABLE")
        if r["source"] not in ids or r["cible"] not in ids or r["source"] == r["cible"]:
            raise ValueError("Import refusé : extrémités invalides")
        if r.get("type") not in RELATIONS_AUTORISEES:
            raise ValueError("Import refusé : prédicat inconnu")
        p = r.get("preuve")
        if not isinstance(p, dict) or not p.get("document") or len(normaliser(p.get("citation"))) < 15:
            raise ValueError("Import refusé : preuve documentaire structurée requise")
        controle = controler_relation(r, {c['id']: c for c in concepts})
        if controle["motifs_rejet"] or any(controle[k] != r[k] for k in ("source", "type", "cible")):
            raise ValueError("Import refusé : recontrôle nécessaire, relation incohérente")
