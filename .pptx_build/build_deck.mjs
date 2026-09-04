import fs from "node:fs/promises";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const OUT = "C:/Users/0404836P/OneDrive - SNCF/AGENT_SNCF/Presentation_GraphRAG_Arianes.pptx";
const PREVIEW = "C:/Users/0404836P/OneDrive - SNCF/AGENT_SNCF/.pptx_build/rendered";
const W = 1280, H = 720;
const C = {
  ink: "#0B1220", muted: "#5E6877", rule: "#CFD5DD", panel: "#EEF1F4",
  blue: "#2F7EF7", lightBlue: "#DCEBFF", cyan: "#58C7E8", white: "#FFFFFF",
  green: "#20A77A", amber: "#F0A43A", red: "#D94A5A", navy: "#102A43"
};

function addText(slide, text, x, y, w, h, size=20, color=C.ink, bold=false, align="left") {
  const s = slide.shapes.add({
    geometry: "textbox", position: { left:x, top:y, width:w, height:h },
    fill: "none", line: { style:"solid", fill:"none", width:0 }
  });
  s.text = text;
  s.text.style = { fontSize:size, typeface:"Arial", color, bold, alignment:align, verticalAlignment:"middle", autoFit:"shrinkText", insets:{top:0,right:0,bottom:0,left:0} };
  return s;
}

function addBox(slide, x, y, w, h, fill=C.white, stroke=C.rule, radius="rounded-xl") {
  return slide.shapes.add({
    geometry:"roundRect", position:{left:x,top:y,width:w,height:h}, fill,
    line:{style:"solid",fill:stroke,width:1.3}, borderRadius:radius
  });
}

function addNode(slide, x, y, w, h, title, subtitle="", fill=C.white, stroke=C.blue, titleSize=22) {
  const box = addBox(slide,x,y,w,h,fill,stroke,"rounded-xl");
  const sombre = fill === C.navy;
  addText(slide,title,x+14,y+10,w-28,subtitle?30:h-20,titleSize,sombre?C.white:C.ink,true,"center");
  if (subtitle) addText(slide,subtitle,x+14,y+42,w-28,h-52,15,sombre?"#D7E4F2":C.muted,false,"center");
  return box;
}

function connect(slide, a, b, from="right", to="left", color=C.blue, dashed=false) {
  return slide.shapes.connect(a,b,{
    kind:"straight", fromSide:from, toSide:to,
    line:{style:dashed?"dashed":"solid",fill:color,width:2.2},
    tail:{type:"arrow",width:"med",length:"med"}
  });
}

function title(slide, heading, kicker="PROJET GRAPHRAG ARIANES") {
  addText(slide,kicker,48,25,500,26,14,C.blue,true);
  addText(slide,heading,48,55,1184,62,38,C.ink,true);
  slide.shapes.add({geometry:"rect",position:{left:48,top:125,width:1184,height:2},fill:C.rule,line:{style:"solid",fill:"none",width:0}});
}

function footer(slide, n) {
  addText(slide,String(n).padStart(2,"0"),1170,680,62,18,12,C.muted,false,"right");
}

function notes(slide, lines, sources) {
  slide.speakerNotes.textFrame.setText([
    ...lines,
    "",
    "[Sources]",
    ...sources.map(s => `- ${s}`),
    "[/Sources]"
  ]);
}

const p = Presentation.create({slideSize:{width:W,height:H}});

// 1 — Couverture : silhouette sparse inspirée de Codex Grid slide 01.
{
  const s=p.slides.add(); s.background.fill=C.white;
  addText(s,"STAGE — INGÉNIERIE DES DONNÉES",48,34,650,28,15,C.blue,true);
  addText(s,"Un assistant GraphRAG\npour le modèle Arianes",48,180,850,190,58,C.ink,true);
  addText(s,"Du squelette UML aux connaissances métier interrogeables",48,430,750,70,25,C.muted);
  const g=addBox(s,925,150,260,350,C.navy,C.navy,"rounded-xl");
  const n1=addNode(s,980,205,150,58,"Classe","métamodèle",C.white,C.white,20);
  const n2=addNode(s,980,300,150,58,"Concept","métier",C.lightBlue,C.lightBlue,20);
  const n3=addNode(s,980,395,150,58,"Chunk","preuve",C.white,C.white,20);
  connect(s,n1,n2,"bottom","top",C.cyan); connect(s,n2,n3,"bottom","top",C.cyan);
  addText(s,"GraphRAG",958,520,196,34,18,C.white,true,"center");
  footer(s,1);
  notes(s,["Présenter le projet en une phrase : rendre un métamodèle complexe et des fiches métier interrogeables en langage naturel."],["README_PROJET.md","BILAN_SCRIPTS_PYTHON.md"]);
}

// 2 — Progression.
{
  const s=p.slides.add(); s.background.fill=C.white; title(s,"Le projet a évolué en quatre étapes");
  const xs=[70,365,660,955];
  const boxes=[];
  const content=[
    ["1", "Squelette UML", "Classes, attributs, héritages et associations"],
    ["2", "Documents", "Fiches découpées en chunks et vectorisées"],
    ["3", "Graphe métier", "Concepts reliés, preuves et conditions"],
    ["4", "Application", "Chat, mémoire, comptes et graphe interactif"]
  ];
  for(let i=0;i<4;i++){
    if(i<3) slideArrow(s,xs[i]+220,345,xs[i+1]-20,345);
    boxes.push(addBox(s,xs[i],205,235,300,i===3?C.lightBlue:C.panel,i===3?C.blue:C.rule,"rounded-xl"));
  }
  for(let i=0;i<4;i++){
    addText(s,content[i][0],xs[i]+20,225,50,50,30,C.blue,true);
    addText(s,content[i][1],xs[i]+20,292,195,45,24,C.ink,true);
    addText(s,content[i][2],xs[i]+20,355,195,100,18,C.muted);
  }
  addText(s,"Le résultat n’est plus un simple chatbot : il combine structure, métier et documentation.",70,560,1100,62,25,C.ink,true,"center");
  footer(s,2);
  notes(s,["Rappeler le dernier point présenté auparavant : le squelette UML.","Montrer ensuite l'enrichissement progressif jusqu'à l'application complète."],["GrapheBuilder_v3.py","pipeline_graphe_metier.py","api.py"]);
}

// 3 — Architecture globale.
{
  const s=p.slides.add(); s.background.fill=C.white; title(s,"Trois sources alimentent une réponse contrôlée");
  const a1=addNode(s,50,180,180,82,"XMI","structure UML",C.panel,C.rule);
  const a2=addNode(s,50,305,180,82,"JSON","modèle normalisé",C.panel,C.rule);
  const a3=addNode(s,50,430,180,82,"Fiches texte","procédures métier",C.panel,C.rule);
  const db=addNode(s,345,240,270,215,"Neo4j","Classes + Documents\n+ Concepts métier",C.navy,C.navy,30);
  const ret=addNode(s,720,275,210,145,"Retriever","sélectionne le sous-graphe\net les passages utiles",C.lightBlue,C.blue,25);
  const llm=addNode(s,1020,195,190,92,"Mistral","formule la réponse",C.panel,C.rule);
  const ui=addNode(s,1020,405,190,92,"Application","chat + visualisation",C.panel,C.rule);
  connect(s,a1,db); connect(s,a2,db); connect(s,a3,db);
  connect(s,db,ret); connect(s,ret,llm); connect(s,llm,ui,"bottom","top");
  addText(s,"Le LLM ne reçoit qu’un contexte extrait du graphe — pas toute la base.",690,555,500,56,23,C.ink,true,"center");
  footer(s,3);
  notes(s,["Insister sur la séparation entre stockage, retrieval et génération.","Le modèle de langage ne connaît pas directement Neo4j : le retriever construit son contexte."],["XmiToJson.py","GrapheBuilder_v3.py","graphrag_retriever.py","Agent_LG.py"]);
}

// 4 — Couches du graphe.
{
  const s=p.slides.add(); s.background.fill=C.white; title(s,"Deux graphes complémentaires donnent du sens aux données");
  addText(s,"COUCHE MÉTIER",65,155,230,28,16,C.blue,true);
  const poste=addNode(s,480,155,230,72,"Poste d’aiguillage","concept métier",C.lightBlue,C.blue);
  const signal=addNode(s,130,255,180,65,"Signal","concept",C.white,C.blue,20);
  const voie=addNode(s,900,255,210,65,"Appareil de voie","concept",C.white,C.blue,20);
  connect(s,signal,poste,"right","left",C.blue); connect(s,voie,poste,"left","right",C.blue);
  addText(s,"EST_COMMANDÉ_PAR",280,215,190,24,14,C.muted,true,"center");
  addText(s,"EST_COMMANDÉ_PAR",718,215,190,24,14,C.muted,true,"center");
  slideLine(s,70,375,1210,375,C.rule,2);
  addText(s,"COUCHE TECHNIQUE",65,395,250,28,16,C.green,true);
  const cp=addNode(s,480,415,230,68,"Classe Poste","métamodèle Arianes",C.panel,C.green);
  const cs=addNode(s,130,520,180,62,"Classe Signal","UML",C.white,C.green,20);
  const cv=addNode(s,900,520,210,62,"Classe AppareilDeVoie","UML",C.white,C.green,18);
  connect(s,cp,cs,"left","right",C.green); connect(s,cp,cv,"right","left",C.green);
  connect(s,poste,cp,"bottom","top",C.amber,true);
  addText(s,"REPRÉSENTE_PAR",755,385,190,25,14,C.amber,true,"center");
  addText(s,"Le métier explique le fonctionnement ; l’UML garantit la structure.",310,625,660,36,23,C.ink,true,"center");
  footer(s,4);
  notes(s,["Montrer que les deux graphes restent séparés mais reliés.","La relation REPRESENTE_PAR rattache un concept métier à une classe du métamodèle."],["graphe_metier_builder.py","graphrag_retriever.py","DataMetier/selection_auto_prudente.json"]);
}

// 5 — Pipeline métier.
{
  const s=p.slides.add(); s.background.fill=C.white; title(s,"Le pipeline métier transforme une fiche en faits vérifiables");
  const steps=[
    ["1", "Découper", "Texte + lignes"],
    ["2", "Détecter", "Entités candidates"],
    ["3", "Extraire", "Relations + preuves"],
    ["4", "Contrôler", "Règles et cohérence"],
    ["5", "Importer", "Seulement VALIDE"]
  ];
  const xs=[45,295,545,795,1045], boxes=[];
  for(let i=0;i<5;i++) boxes.push(addBox(s,xs[i],230,190,245,i===4?C.lightBlue:C.panel,i===4?C.blue:C.rule,"rounded-xl"));
  for(let i=0;i<4;i++) connect(s,boxes[i],boxes[i+1]);
  for(let i=0;i<5;i++){
    addText(s,steps[i][0],xs[i]+18,248,40,38,26,C.blue,true);
    addText(s,steps[i][1],xs[i]+18,305,154,35,23,C.ink,true);
    addText(s,steps[i][2],xs[i]+18,360,154,65,17,C.muted,false,"center");
  }
  addText(s,"Une relation sans preuve, ambiguë ou incohérente reste hors du graphe actif.",145,535,990,55,25,C.ink,true,"center");
  footer(s,5);
  notes(s,["Expliquer que Mistral propose, mais ne valide pas seul.","Les contrôles déterministes vérifient citation, concepts, prédicat, négation et auto-relations."],["pipeline_graphe_metier.py","validation_metier.py","recontroler_graphe_metier.py","selectionner_graphe_metier_prudent.py"]);
}

// 6 — Retrieval.
{
  const s=p.slides.add(); s.background.fill=C.white; title(s,"Une question déclenche un retrieval hybride avant la génération");
  const q=addNode(s,65,275,200,112,"Question","« Relations du poste ? »",C.navy,C.navy,24);
  const e=addNode(s,350,170,220,95,"1. Entités","Poste / poste_aiguillage",C.panel,C.rule,22);
  const g=addNode(s,350,405,220,95,"2. Graphe","voisins + relations",C.panel,C.rule,22);
  const c=addNode(s,665,170,220,95,"3. Chunks","passages pertinents",C.panel,C.rule,22);
  const ctx=addNode(s,665,405,220,95,"4. Contexte","fusion contrôlée",C.lightBlue,C.blue,22);
  const r=addNode(s,985,275,220,112,"Réponse","courte et ciblée",C.navy,C.navy,24);
  connect(s,q,e); connect(s,q,g); connect(s,e,c); connect(s,g,ctx); connect(s,c,ctx,"bottom","top"); connect(s,ctx,r);
  addText(s,"Structure + sens métier + documentation",420,570,500,42,24,C.blue,true,"center");
  footer(s,6);
  notes(s,["Le mode peut être structurel, documentaire ou hybride.","L'historique récent complète la question pour assurer la mémoire dans une conversation."],["graphrag_retriever.py","Agent_LG.py","api.py"]);
}

// 7 — Résultats, silhouette métrique inspirée de slide 19.
{
  const s=p.slides.add(); s.background.fill=C.white; title(s,"Le prototype couvre désormais toute la chaîne");
  const metrics=[
    ["998", "classes UML", C.blue],
    ["244", "chunks indexés", C.cyan],
    ["114", "concepts métier", C.green],
    ["120", "relations métier", C.amber]
  ];
  const xs=[55,355,655,955];
  for(let i=0;i<4;i++){
    addBox(s,xs[i],190,270,235,C.panel,C.rule,"rounded-xl");
    addText(s,metrics[i][0],xs[i]+20,220,230,85,48,metrics[i][2],true,"center");
    addText(s,metrics[i][1],xs[i]+20,325,230,50,21,C.ink,true,"center");
  }
  addText(s,"57 tests automatisés",120,505,300,48,28,C.ink,true,"center");
  addText(s,"Comptes et mémoire",490,505,300,48,28,C.ink,true,"center");
  addText(s,"Graphe interactif",860,505,300,48,28,C.ink,true,"center");
  addText(s,"Limite actuelle : 17 composantes métier, car les liens transversaux restent prudents.",160,610,960,38,20,C.muted,false,"center");
  footer(s,7);
  notes(s,["Présenter ces chiffres comme l'état du prototype, pas comme des objectifs définitifs.","La fragmentation du graphe évite d'inventer des liens uniquement pour le rendre connexe."],["Résultats Neo4j observés dans la session","Suite pytest observée dans la session","api.py","index.html"]);
}

// 8 — Conclusion / démonstration.
{
  const s=p.slides.add(); s.background.fill=C.white;
  addText(s,"À retenir",48,32,420,35,17,C.blue,true);
  addText(s,"Le graphe apporte la structure.\nLes fiches apportent le métier.\nLe GraphRAG relie les deux.",48,125,870,220,46,C.ink,true);
  const b1=addBox(s,55,455,340,130,C.panel,C.rule,"rounded-xl");
  const b2=addBox(s,470,455,340,130,C.lightBlue,C.blue,"rounded-xl");
  const b3=addBox(s,885,455,340,130,C.panel,C.rule,"rounded-xl");
  addText(s,"1",75,470,35,35,24,C.blue,true); addText(s,"Poser une question",75,515,285,32,22,C.ink,true);
  addText(s,"2",490,470,35,35,24,C.blue,true); addText(s,"Afficher le sous-graphe",490,515,285,32,22,C.ink,true);
  addText(s,"3",905,470,35,35,24,C.blue,true); addText(s,"Vérifier la réponse",905,515,285,32,22,C.ink,true);
  addText(s,"Démonstration : « Donne-moi les relations métier d’un poste d’aiguillage. »",160,625,960,38,20,C.muted,false,"center");
  footer(s,8);
  notes(s,["Terminer par une démonstration courte dans le navigateur.","Question, réponse directe, puis bouton Voir le graphe pour montrer les concepts surlignés."],["Application locale http://127.0.0.1:8000","README_PROJET.md"]);
}

function slideLine(slide,x1,y1,x2,y2,color=C.rule,width=2){
  return slide.shapes.add({geometry:"line",position:{left:x1,top:y1,width:x2-x1,height:y2-y1},line:{style:"solid",fill:color,width}});
}
function slideArrow(slide,x1,y1,x2,y2){
  const a=slide.shapes.add({geometry:"chevron",position:{left:x1,top:y1-11,width:Math.max(30,x2-x1),height:22},fill:C.blue,line:{style:"solid",fill:"none",width:0}});
  return a;
}

await fs.mkdir(PREVIEW,{recursive:true});
for (const [i,slide] of p.slides.items.entries()) {
  const blob=await p.export({slide,format:"png",scale:1});
  await fs.writeFile(`${PREVIEW}/slide-${i+1}.png`,new Uint8Array(await blob.arrayBuffer()));
  const layout=await slide.export({format:"layout"});
  await fs.writeFile(`${PREVIEW}/slide-${i+1}.layout.json`,await layout.text());
}
const montage=await p.export({format:"webp",montage:true,scale:1});
await fs.writeFile("C:/Users/0404836P/OneDrive - SNCF/AGENT_SNCF/.pptx_build/montage.webp",new Uint8Array(await montage.arrayBuffer()));
const pptx=await PresentationFile.exportPptx(p);
await pptx.save(OUT);
console.log(`Créé: ${OUT}`);
