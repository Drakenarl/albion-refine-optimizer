import type { ReactNode } from 'react'

// Definitions pedagogiques des termes techniques exposes par l'UI. Centralise
// ici pour eviter de dupliquer les textes et garder un vocabulaire coherent
// dans tous les composants.

export const GLOSSARY: Record<string, ReactNode> = {
  roi_capital: (
    <>
      <p>
        <strong>ROI capital = bénéfice / capital total investi.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        C'est le vrai retour sur investissement de la banque : ce que tu gagnes
        divisé par ce que tu as dû sortir (achat brut + achat T-1 + coût station).
        Contrairement à la marge V1, il ne déduit pas la récup RRR du capital.
      </p>
    </>
  ),

  marge_efficacite: (
    <>
      <p>
        <strong>Marge efficacité = bénéfice / (capital − récup RRR).</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Métrique héritée V1. Utile pour mesurer l'efficacité du process de
        raffinage, mais trompeuse comme ROI réel : elle gonfle le rendement
        parce qu'elle retire la récup du dénominateur.
      </p>
    </>
  ),

  rrr_effectif: (
    <>
      <p>
        <strong>Return Rate on Resources appliqué à ce run.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Probabilité qu'une ressource soit rendue au raffineur. Base ~15%, boostée
        par la ville spécialité (+~36%) et le focus (+59%). Un RRR effectif de
        53.9% veut dire qu'en moyenne 53.9% de tes matières reviennent.
      </p>
    </>
  ),

  recup_rrr: (
    <>
      <p>
        <strong>Valorisation de ce que le RRR t'a rendu.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Les matières bonus sont revendues au top buy order de la ville indiquée.
        Le montant affiché est net (déduction faite de la freshness du carnet).
        Avec <span className="num">--recup-mode with-planks</span>, la vente se
        fait à la ville de destination des planks/cuirs.
      </p>
    </>
  ),

  instant_sell: (
    <>
      <p>
        <strong>Vente immédiate au top buy order.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Scénario safe : le silver tombe tout de suite. Le revenu est plafonné
        par le meilleur buy order du carnet. Peu de risque, mais moins profitable
        qu'un sell order rempli.
      </p>
    </>
  ),

  sell_order: (
    <>
      <p>
        <strong>Vente en attente à ton propre prix (undercut).</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Scénario opportuniste : tu poses un sell order sous le top sell existant.
        Le revenu affiché est <em>espéré</em> — pondéré par la probabilité de
        fill estimée depuis le volume 24h et la profondeur du carnet.
      </p>
    </>
  ),

  freshness_factor: (
    <>
      <p>
        <strong>Facteur de confiance basé sur l'âge de la donnée.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Un prix vieux de 6h+ est moins fiable qu'un prix de 15 min : ce facteur
        (0.6 à 1.0) décote le revenu prévu en conséquence. C'est pour ça qu'un
        carnet frais peut battre un carnet plus rémunérateur mais périmé.
      </p>
    </>
  ),

  fill_proba: (
    <>
      <p>
        <strong>Probabilité que ton sell order soit rempli.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Estimée depuis le volume 24h et la profondeur du carnet à ton prix
        cible. En dessous de 40%, le scénario est grisé — signal qu'il vaut
        mieux prendre l'instant sell.
      </p>
    </>
  ),

  silver_par_focus: (
    <>
      <p>
        <strong>Bénéfice net par point de focus dépensé.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Métrique clé quand ton facteur limitant est le focus (pas la silver).
        Un run à faible ROI mais fort silver/focus peut être meilleur qu'un run
        rentable qui grille tout ton focus pour rien.
      </p>
    </>
  ),

  seuil_roi: (
    <>
      <p>
        <strong>Plancher de ROI capital pour retenir une route.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        À 0%, toute route rentable passe. À 20%, seules les routes avec 20% de
        retour minimum sont affichées. C'est un plancher, pas un objectif : les
        routes affichées peuvent être meilleures que le seuil.
      </p>
    </>
  ),

  buy_slippage: (
    <>
      <p>
        <strong>Inflation appliquée au prix d'achat AODP.</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        AODP n'expose que <span className="num">sell_price_min</span> (le top du
        carnet), pas la quantité disponible à ce prix. Sur un carnet réel, il y a
        souvent 2 unités à 370 puis un mur à 400.
      </p>
      <p className="mt-1.5 text-ink-muted">
        Le prix effectif utilisé pour la ROI est donc gonflé de deux composantes :
      </p>
      <ul className="mt-1 list-disc pl-4 text-ink-muted">
        <li>
          <strong>Profondeur</strong> : ratio quantité demandée / volume 24h. De
          0% (marché épais) à +20% (tu veux le double du volume 24h).
        </li>
        <li>
          <strong>Fraîcheur</strong> : âge de la donnée AODP. De 0% (&lt; 30 min) à
          +15% (&gt; 4h).
        </li>
      </ul>
      <p className="mt-1.5 text-ink-muted">
        Total plafonné à +25% pour éviter de tuer une route sur un chiffre
        théorique. Si l'inflation dépasse 8%, un warning s'affiche pour te faire
        vérifier le carnet en jeu.
      </p>
    </>
  ),

  enchant: (
    <>
      <p>
        <strong>Niveau d'enchantement de la matière (.0 à .4).</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        .0 = base, .1 à .4 = variantes enchantées. La recette et les formules
        de raffinage sont identiques ; seuls les item IDs AODP changent
        (T7_WOOD_LEVEL1@1 par ex.). Un T7 .2 plank consomme du T7 .2 wood et
        du T6 .2 planks — jamais du base.
      </p>
      <p className="mt-1.5 text-ink-muted">
        En pratique : peu de refineurs touchent aux enchants (barrière capital
        + focus), donc le marché est moins saturé et les marges peuvent être
        bien meilleures qu'en base. Contrepartie : volumes 24h plus faibles,
        risque de fill sur sell order plus élevé.
      </p>
    </>
  ),

  station_rate: (
    <>
      <p>
        <strong>Coût de la station de raffinage (silver / 100 nutrition).</strong>
      </p>
      <p className="mt-1.5 text-ink-muted">
        Fixé par le propriétaire de l'île en jeu. La valeur communément vue est
        50 silver, mais elle varie selon la ville et l'heure. Vérifie sur ta
        station habituelle avant de committer.
      </p>
    </>
  ),
}
