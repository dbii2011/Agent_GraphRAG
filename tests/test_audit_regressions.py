from unittest.mock import Mock

from arianes.graph.uml_builder import ArianeGraphBuilder, parser_nom_fichier
from arianes.pipelines.xmi_to_json import deduplique, parse_xmi
from arianes.pipelines.validation_metier import controler_relation


def test_stub_does_not_replace_description():
    stub = dict(nom="Ligne", description="Élément externe (Class)", abstraite=False, attributs=[])
    full = dict(nom="Ligne", description="Définition complète", abstraite=True, attributs=[])
    for entries in ([dict(stub), dict(full)], [dict(full), dict(stub)]):
        assert deduplique(entries)[0]["description"] == "Définition complète"


def test_roles_are_part_of_relation_identity():
    builder = ArianeGraphBuilder.__new__(ArianeGraphBuilder)
    builder._run = Mock()
    for role in ("debut", "fin"):
        builder.add_relation("A", "ASSOCIE_A", "B", role, "0..*")
    calls = builder._run.call_args_list
    assert all("{role: $role}" in c.args[0] for c in calls)
    assert [c.kwargs["role"] for c in calls] == ["debut", "fin"]
    assert all(c.kwargs["card"] == "0..*" for c in calls)


def test_windows_and_posix_document_names():
    assert parser_nom_fichier(r"C:\Docs\Ligne_test.txt") == ("Ligne", "test")
    assert parser_nom_fichier("/docs/Ligne_test.txt") == ("Ligne", "test")


def test_no_correction_is_not_direction_confirmation():
    concepts = {x: dict(nom=x, categorie="EQUIPEMENT") for x in ("a", "b")}
    citation = "Cet équipement est un équipement ferroviaire."
    result = controler_relation(dict(source="a", cible="b", type="EST_UN",
                                    preuve=dict(citation=citation)), concepts, citation)
    assert result["statut"] == "PROBABLE"
    assert result["criteres"]["direction_confirmee"] is False


def test_xmi_forward_reference(tmp_path):
    source = tmp_path / "sample.xml"
    source.write_text('''<root xmlns:UML="omg.org/UML1.3">
      <UML:Class xmi.id="a" name="A"><UML:Attribute name="b" type="b"/></UML:Class>
      <UML:Class xmi.id="b" name="B"/>
    </root>''', encoding="utf-8")
    classes, _, _, _ = parse_xmi(source)
    assert classes[0]["attributs"][0]["type"] == "B"
