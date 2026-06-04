# Instagram - Documentation dediee

<div class="doc-hero">
  <div class="doc-kicker">Section Instagram</div>
  <p>Cette section de `taktik-docs` est dediee a Instagram. Elle n'est pas une documentation separee : elle organise le fonctionnement Instagram dans TAKTIK avec le contexte Bot + Electron : workflows, handlers Electron, bridges Python, Bot Android, sessions, donnees, live, debug et dependances partagees vues depuis Instagram.</p>
  <p>Le but est simple : permettre a quelqu'un qui n'a jamais lu de doc technique de comprendre l'arbre des modules Instagram, puis de descendre progressivement vers l'implementation.</p>
</div>

## Commencer par le metier

<div class="doc-grid">
  <a class="doc-card" href="#/workflow-map">
    <div class="doc-kicker">Carte</div>
    <h3>Vue d'ensemble des workflows</h3>
    <p>Le meilleur point de depart pour voir les familles Instagram et leurs imbrications.</p>
  </a>
  <a class="doc-card" href="#/automation">
    <div class="doc-kicker">Automation</div>
    <h3>Targets, hashtags, feed, post URL</h3>
    <p>Comprendre les workflows qui partent d'une cible et executent des actions automatiques.</p>
  </a>
  <a class="doc-card" href="#/engagement">
    <div class="doc-kicker">Engagement</div>
    <h3>DM, cold DM, comments</h3>
    <p>Voir l'arbre des interactions directes et leurs contraintes de persistance.</p>
  </a>
  <a class="doc-card" href="#/publishing">
    <div class="doc-kicker">Publishing</div>
    <h3>Post, reel, story</h3>
    <p>Suivre le chemin media -> caption -> Android -> event live -> statut final.</p>
  </a>
  <a class="doc-card" href="#/scraping">
    <div class="doc-kicker">Scraping</div>
    <h3>Scraping et qualification</h3>
    <p>Voir d'ou viennent les donnees Instagram et comment elles sont reutilisees.</p>
  </a>
  <a class="doc-card" href="#/shared-modules">
    <div class="doc-kicker">Dependances</div>
    <h3>Modules partages utilises par Instagram</h3>
    <p>Comprendre les briques communes sans quitter le contexte Instagram.</p>
  </a>
</div>

## Chantiers transverses

<div class="doc-grid">
  <a class="doc-card" href="#/bot-core-refactor-tracker">
    <div class="doc-kicker">Transverse</div>
    <h3>Suivi refactor Bot core</h3>
    <p>Voir l'avancement global de <code>bot/taktik/core</code> sans le confondre avec la seule architecture Instagram.</p>
  </a>
</div>

## Ensuite seulement: le detail technique

<div class="doc-grid">
  <a class="doc-card" href="#/architecture">
    <div class="doc-kicker">Architecture</div>
    <h3>Arbre d'imbrication complet</h3>
    <p>Page technique pour voir comment UI, handlers, bridges, Bot et SQLite s'enchainent.</p>
  </a>
  <a class="doc-card" href="#/class-map">
    <div class="doc-kicker">Classes</div>
    <h3>Heritage et modules partages</h3>
    <p>Voir les classes pivots, les mixins, les bridges et les services reutilises par Instagram.</p>
  </a>
  <a class="doc-card" href="#/workflow-deep-dive">
    <div class="doc-kicker">Deep dive</div>
    <h3>Fonctionnement complet des workflows</h3>
    <p>Suivre les workflows Instagram importants avec sequences, payloads, events et DB.</p>
  </a>
  <a class="doc-card" href="#/electron-runtime">
    <div class="doc-kicker">Electron</div>
    <h3>Runtime desktop</h3>
    <p>Comprendre comment le desktop Instagram construit le payload, lance et stoppe les runs.</p>
  </a>
  <a class="doc-card" href="#/bot-runtime">
    <div class="doc-kicker">Bot</div>
    <h3>Runtime Android</h3>
    <p>Comprendre selectors, actions et workflows du Bot Instagram.</p>
  </a>
  <a class="doc-card" href="#/bridges">
    <div class="doc-kicker">Bridges</div>
    <h3>Orchestration Python</h3>
    <p>Voir les bridges Instagram qui relient Electron et Bot.</p>
  </a>
  <a class="doc-card" href="#/selectors">
    <div class="doc-kicker">Compat</div>
    <h3>Selectors et stabilite</h3>
    <p>Comprendre les zones les plus sensibles aux regressions UI Instagram.</p>
  </a>
  <a class="doc-card" href="#/scheduler-sessions-live">
    <div class="doc-kicker">Live</div>
    <h3>Scheduler, sessions et Live Center</h3>
    <p>Suivre run manuel, run planifie, etats live et stop/cancel.</p>
  </a>
  <a class="doc-card" href="#/data-contracts">
    <div class="doc-kicker">Data</div>
    <h3>Donnees, repositories et sync</h3>
    <p>Voir ce qui est persiste, synchronise et affiche dans les vues de donnees.</p>
  </a>
  <a class="doc-card" href="#/debug-compat">
    <div class="doc-kicker">Debug</div>
    <h3>Dumps, mirror et compatibilite</h3>
    <p>Retrouver les outils de diagnostic quand Instagram ne se comporte pas comme prevu.</p>
  </a>
  <a class="doc-card" href="#/quality-audit">
    <div class="doc-kicker">Qualite</div>
    <h3>Dette et refactor</h3>
    <p>Reperer les zones ou l'architecture Instagram doit etre durcie.</p>
  </a>
  <a class="doc-card" href="#/cartography-coverage">
    <div class="doc-kicker">Checkpoint</div>
    <h3>Couverture de cartographie</h3>
    <p>Savoir ce qui est prouve, ce qui reste a tracer, et quels chantiers peuvent demarrer.</p>
  </a>
  <a class="doc-card" href="#/audit-remediation-plan">
    <div class="doc-kicker">Plan</div>
    <h3>Colmater les bugs critiques</h3>
    <p>Transformer l'audit en plan de correction verifiable, point par point.</p>
  </a>
  <a class="doc-card" href="#/architecture-target-orm">
    <div class="doc-kicker">Architecture cible</div>
    <h3>POO, ORM et modele domaine</h3>
    <p>Preparer une trajectoire type Symfony/Doctrine sans migration big bang.</p>
  </a>
  <a class="doc-card" href="#/selectors-audit-plan">
    <div class="doc-kicker">Selectors</div>
    <h3>Pages, modales et recherche texte</h3>
    <p>Auditer chaque detection UI Instagram comme un contrat testable.</p>
  </a>
  <a class="doc-card" href="#/performance-humanization">
    <div class="doc-kicker">Bot engine</div>
    <h3>Performance et actions humaines</h3>
    <p>Identifier les gains de vitesse et definir un moteur d'action plus naturel.</p>
  </a>
  <a class="doc-card" href="#/feature-spec-template">
    <div class="doc-kicker">Feature</div>
    <h3>Template de cadrage</h3>
    <p>Preparer une nouvelle feature sans casser l'existant.</p>
  </a>
</div>

## Regle de lecture

1. Commencer par [Carte des workflows](workflow-map.md).
2. Ouvrir la famille Instagram concernee.
3. Lire [Couverture de cartographie](cartography-coverage.md) avant de corriger un bug ou refactorer.
4. Descendre ensuite vers [Architecture Instagram](architecture.md) et les pages runtime seulement si on touche au code.

## Principe

Si un concept partage est utile a Instagram, on l'explique ici en tant que dependance d'Instagram. La source reste `taktik-docs`; cette section evite seulement au lecteur de traverser toute la doc transverse pour comprendre le coeur du fonctionnement Instagram.
