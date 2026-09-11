import glob
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date
import glob

from arianes.paths import UML_DATA_DIR, XMI_DATA_DIR

NS = "omg.org/UML1.3"
DATA_DIR = UML_DATA_DIR
XMI_DIR = XMI_DATA_DIR


def tag(name):
    return f"{{{NS}}}{name}"


def get_documentation(element):
    for tv in element.iter(tag("TaggedValue")):
        if tv.get("tag") in ["documentation", "description", "comment"]:
            val = tv.get("value")
            if val:
                return val.strip()
    for comment in element.iter(tag("Comment")):
        name = comment.get("name")
        if name:
            return name.strip()
    return ""

def est_une_enumeration(element):
    if element.get("stereotype") and element.get("stereotype").lower() == "enumeration":
        return True
    for stereo in element.iter(tag("Stereotype")):
        name = stereo.get("name")
        if name and name.lower() == "enumeration":
            return True
    return False


def get_multiplicity(element):
    for mr in element.iter(tag("MultiplicityRange")):
        lower = mr.get("lower") or "0"
        upper = mr.get("upper") or "*"
        if upper == "-1":
            upper = "*"
        return lower, upper
    return "0", "*"


def parse_xmi(path):
    tree = ET.parse(path)
    root = tree.getroot()

    id_to_name = {}
    classes = []
    generalizations = []
    relations = []
    enums = []

    # Résoudre aussi les types déclarés après les attributs qui les utilisent.
    for element in root.iter():
        xid = element.get("xmi.id") or element.get("id")
        if xid and element.get("name"):
            id_to_name[xid] = element.get("name")

    for stub in list(root.iter(tag("EAStub"))) + list(root.iter("EAStub")):
        xid = stub.get("xmi.id") or stub.get("id")
        name = stub.get("name")
        uml_type = stub.get("UMLType") or "Class"  
        
        if xid and name:
            id_to_name[xid] = name
            if uml_type.lower() == "enumeration":
                enums.append({"nom": name, "valeurs": []})
                
            elif uml_type.lower() in ["class", "interface"]:
                classes.append({
                    "nom": name, 
                    "abstraite": False, 
                    "description": f"Élément externe ({uml_type})", 
                    "attributs": []
                })

    for dt in root.iter(tag("DataType")):
        xid = dt.get("xmi.id")
        name = dt.get("name")
        if xid and name:
            id_to_name[xid] = name

    for enum in root.iter(tag("Enumeration")):
        name = enum.get("name")
        xid = enum.get("xmi.id")
        if not name or not xid:
            continue
        id_to_name[xid] = name
        
        valeurs = []
        for lit in enum.iter(tag("EnumerationLiteral")):
            lit_name = lit.get("name")
            if lit_name:
                valeurs.append(lit_name)
        enums.append({"nom": name, "valeurs": valeurs})

    for cls in root.iter(tag("Class")):
        name = cls.get("name")
        xid = cls.get("xmi.id")
        if not name or not xid:
            continue
        id_to_name[xid] = name

        if est_une_enumeration(cls):
            valeurs = []
            for attr in cls.iter(tag("Attribute")):
                lit_name = attr.get("name")
                if lit_name:
                    valeurs.append(lit_name)
            enums.append({"nom": name, "valeurs": valeurs})
            continue
        
        cls_desc = get_documentation(cls)
        
        attributs = []
        for attr in cls.iter(tag("Attribute")):
            attr_name = attr.get("name")
            if not attr_name:
                continue
            
            attr_type = None
            if attr.get("type"):
                t_id = attr.get("type")
                attr_type = id_to_name.get(t_id, t_id)
            else:
                for child in attr.iter():
                    idref = child.get("xmi.idref")
                    if idref and idref in id_to_name:
                        attr_type = id_to_name[idref]
                        break
            
            lower, _ = get_multiplicity(attr)
            obligatoire = lower == "1"
            
            attr_data = {
                "nom": attr_name, 
                "type": attr_type, 
                "description": get_documentation(attr)
            }
            if obligatoire:
                attr_data["obligatoire"] = True
                
            for init in attr.iter(tag("Expression")):
                if init.get("body"):
                    attr_data["defaut"] = init.get("body")

            attributs.append(attr_data)

        classes.append({
            "nom": name, 
            "abstraite": cls.get("isAbstract") == "true",
            "description": cls_desc,
            "attributs": attributs
        })

    for gen in root.iter(tag("Generalization")):
        sub = gen.get("subtype")
        sup = gen.get("supertype")
        if sub in id_to_name and sup in id_to_name:
            generalizations.append({"source": id_to_name[sub], "cible": id_to_name[sup]})

    for assoc in root.iter(tag("Association")):
        conn = assoc.find(tag("Association.connection"))
        if conn is None:
            continue
        ends = conn.findall(tag("AssociationEnd"))
        if len(ends) != 2:
            continue

        e_src, e_tgt = ends[0], ends[1]
        src_id, tgt_id = e_src.get("type"), e_tgt.get("type")
        if src_id not in id_to_name or tgt_id not in id_to_name:
            continue

        src_nom, tgt_nom = id_to_name[src_id], id_to_name[tgt_id]
        role = e_tgt.get("name") or e_src.get("name")
        agg_src = e_src.get("aggregation", "none")
        agg_tgt = e_tgt.get("aggregation", "none")

        l_src, u_src = get_multiplicity(e_src)
        l_tgt, u_tgt = get_multiplicity(e_tgt)
        card_src = f"{l_src}..{u_src}" if l_src != u_src else l_src
        card_tgt = f"{l_tgt}..{u_tgt}" if l_tgt != u_tgt else l_tgt

        if agg_src == "composite" or agg_tgt == "composite":
            rel_type = "COMPOSE_DE"
            # Si src est le parent (composite), la flèche part de src vers tgt
            source, cible = (src_nom, tgt_nom) if agg_src == "composite" else (tgt_nom, src_nom)
            card = card_tgt if agg_src == "composite" else card_src
            role = e_tgt.get("name") if agg_src == "composite" else e_src.get("name")

        elif agg_src == "shared" or agg_tgt == "shared":
            rel_type = "AGREGE"
            # Si src est le parent (shared), la flèche part de src vers tgt
            source, cible = (src_nom, tgt_nom) if agg_src == "shared" else (tgt_nom, src_nom)
            card = card_tgt if agg_src == "shared" else card_src
            role = e_tgt.get("name") if agg_src == "shared" else e_src.get("name")

        else:
            rel_type = "ASSOCIE_A"
            source, cible = src_nom, tgt_nom
            card = card_tgt

        relations.append({
            "source": source, 
            "type": rel_type, 
            "cible": cible, 
            "role": role, 
            "cardinalite": card
        })

    return classes, generalizations, relations, enums


def deduplique(classes):
    vues = {}
    for c in classes:
        if c["nom"] not in vues:
            vues[c["nom"]] = c
        else:
            if c["abstraite"]:
                vues[c["nom"]]["abstraite"] = True
            if c["description"] and (not vues[c["nom"]]["description"] or (
                vues[c["nom"]]["description"].startswith("Élément externe")
                and not c["description"].startswith("Élément externe")
            )):
                vues[c["nom"]]["description"] = c["description"]
                
            noms_attributs_existants = {a["nom"] for a in vues[c["nom"]]["attributs"]}
            for attr in c["attributs"]:
                if attr["nom"] not in noms_attributs_existants:
                    vues[c["nom"]]["attributs"].append(attr)
                    noms_attributs_existants.add(attr["nom"])
    return list(vues.values())

def read_xmi_file(xmi_path):
    nom_base = os.path.splitext(os.path.basename(xmi_path))[0]
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, f"{nom_base}.json")

    classes, generalizations, relations, enums = parse_xmi(xmi_path)
    classes = deduplique(classes)

    modele_complet = {
        "enums": enums,
        "classes": classes,
        "generalizations": generalizations,
        "relations": relations
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(modele_complet, f, indent=4, ensure_ascii=False)
    print(f"  → {len(classes)} classes, {len(enums)} enums, {len(relations)} relations exportées vers {out_path}")



def main():

    fichiers_xmi = sorted(glob.glob(f"{XMI_DIR}/*.txt"))

    if not fichiers_xmi:
        print(f"Aucun fichier XMI trouvé dans '{XMI_DIR}'.")
        return

    print(f"{len(fichiers_xmi)} fichier(s) trouvé(s) dans '{XMI_DIR}'.")

    for fichier in fichiers_xmi:
        print(f"\n--- Traitement de {fichier} ---")
        try:
            read_xmi_file(fichier)
        except Exception as e:
            print(f"Erreur lors de l'import de {fichier} : {e}")
    print("\nImportation de tous les fichiers terminée.")

if __name__ == "__main__":
    main()
