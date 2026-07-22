import { useEffect, type FC } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowRight,
  Coins,
  Factory,
  Info,
  Lightbulb,
  Layers,
  Sparkles,
  Timer,
  TrendingUp,
  Wand2,
  X,
} from 'lucide-react'

interface Props {
  open: boolean
  onClose: () => void
}

// Guide pedagogique pour un joueur qui debarque sur le trading Albion.
// Volontairement long : c'est du contenu didactique, pas une doc technique.
// Structure : hook -> comment lire une card -> les termes techniques -> reco.
const HowItWorksModal: FC<Props> = ({ open, onClose }) => {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    // Empeche le scroll de la page en dessous.
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-surface-sunken/85 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.article
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="my-8 w-full max-w-3xl rounded-xl border border-surface-border bg-surface-raised shadow-card"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header sticky */}
            <header className="sticky top-0 z-10 flex items-center justify-between gap-4 rounded-t-xl border-b border-surface-border/60 bg-surface-raised/95 px-6 py-4 backdrop-blur">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-primary-500/15 p-2 text-primary-300">
                  <Lightbulb className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">Comment ça marche</h2>
                  <p className="text-xs text-ink-muted">
                    Un guide rapide pour comprendre le raffinage et le trading Albion.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Fermer"
                className="rounded-md p-1.5 text-ink-muted transition hover:bg-surface hover:text-ink"
              >
                <X className="h-5 w-5" />
              </button>
            </header>

            <div className="space-y-8 px-6 py-6 text-sm leading-relaxed text-ink">
              <Section icon={<Coins className="h-4 w-4" />} title="C'est quoi ce site, en une phrase ?">
                <p>
                  Cet outil te dit <strong>où acheter tes ressources, où les raffiner et où
                  revendre les raffinés</strong> pour maximiser ton silver, sur les 6 villes
                  Royal du continent (Fort Sterling, Martlock, Lymhurst, Thetford, Bridgewatch,
                  Caerleon).
                </p>
                <p className="mt-2 text-ink-muted">
                  Il interroge en direct le marché via le{' '}
                  <span className="num">Albion Online Data Project</span>, applique les formules
                  de RRR (return rate), taxes et récup, et te ressort les 3 meilleures routes.
                </p>
              </Section>

              <Section icon={<Factory className="h-4 w-4" />} title="Le raffinage Albion en 60 secondes">
                <p>
                  Raffiner, c'est transformer une <strong>ressource brute</strong> (bois, peau,
                  fibre, minerai, pierre) en <strong>ressource raffinée</strong> (plank, cuir,
                  tissu, lingot, bloc) à une station en ville.
                </p>
                <p className="mt-2">Trois trucs à savoir :</p>
                <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-ink-muted">
                  <li>
                    Chaque tier a une <strong>recette précise</strong>. Un T5 plank demande{' '}
                    <span className="num">3 T5 wood + 1 T4 plank</span>. Un T7 demande{' '}
                    <span className="num">5 T7 wood + 1 T6 plank</span>.
                  </li>
                  <li>
                    La station coûte du silver (basé sur la nutrition et le rate fixé par le
                    proprio de l'île — <span className="num">50 s / 100 nutrition</span> est
                    courant).
                  </li>
                  <li>
                    Une partie des ressources t'est <strong>rendue</strong> après raffinage.
                    C'est le RRR — voir plus bas.
                  </li>
                </ol>
                <Callout tone="info">
                  <strong>Chaque ville a sa spécialité :</strong> bois à Fort Sterling, peau à
                  Martlock, fibre à Lymhurst, minerai à Thetford, pierre à Bridgewatch. Refiner
                  dans la ville spécialité apporte un bonus RRR de{' '}
                  <span className="num">+40%</span> — d'où l'intérêt de bouger.
                </Callout>
              </Section>

              <Section icon={<Layers className="h-4 w-4" />} title="Comment lire une route">
                <p>Chaque card = une combinaison achat + raffinage + vente évaluée par l'outil :</p>
                <div className="mt-3 space-y-3 rounded-lg border border-surface-border/60 bg-surface/40 p-4 font-mono text-xs">
                  <BadgedLine badge="1" title="Achat bois">
                    Où acheter la matière première (au meilleur sell order).
                  </BadgedLine>
                  <BadgedLine badge="2" title="Achat plank T-1">
                    Où acheter le raffiné du tier inférieur (nécessaire à la recette).
                  </BadgedLine>
                  <BadgedLine badge="3" title="Raffinage @ ville spé">
                    Ville où tu vas raffiner. Le RRR effectif est affiché ici.
                  </BadgedLine>
                  <BadgedLine badge="4" title="Vente : instant / sell order">
                    Deux scénarios de vente côte à côte (voir plus bas).
                  </BadgedLine>
                  <BadgedLine badge="5" title="Récup RRR">
                    Valorisation de ce que le RRR t'a rendu (revendu au top buy).
                  </BadgedLine>
                </div>
                <p className="mt-3 text-ink-muted">
                  En haut de card, l'important : <strong>Capital dépensé → Bénéfice safe</strong>{' '}
                  et <strong>ROI capital</strong>. Vert = gagnant, rouge = perdant. C'est ce que
                  ta banque va vraiment voir.
                </p>
              </Section>

              <Section icon={<Sparkles className="h-4 w-4" />} title="Le RRR (Return Rate on Resources)">
                <p>
                  Le RRR, c'est la probabilité que la station te <strong>rende</strong> tes
                  matières après raffinage. Autrement dit : tu ne consommes pas vraiment 100% de
                  ton bois.
                </p>
                <div className="mt-3 space-y-1.5 rounded-lg border border-surface-border/60 bg-surface/40 p-3 text-xs text-ink-muted">
                  <p>
                    <strong className="text-ink">Base :</strong> ~15.2% de retour sur toute
                    station.
                  </p>
                  <p>
                    <strong className="text-ink">+ Ville de raffinage :</strong> +18% dans
                    n'importe quelle ville de crafting.
                  </p>
                  <p>
                    <strong className="text-ink">+ Spécialité :</strong> +40% si tu raffines dans
                    la ville spé (bois à Fort Sterling, etc).
                  </p>
                  <p>
                    <strong className="text-ink">+ Focus :</strong> +59% quand tu actives ton
                    focus premium.
                  </p>
                </div>
                <p className="mt-3">
                  Résultat concret : avec spécialité + focus, tu récupères ~<span className="num">54%</span>{' '}
                  de tes matières. La récup a une vraie valeur — l'outil la revend au top buy
                  order et déduit ça de ton coût.
                </p>
              </Section>

              <Section icon={<TrendingUp className="h-4 w-4" />} title="ROI capital vs marge efficacité">
                <p>
                  Les deux chiffres qui ressemblent à des ROI ne mesurent PAS la même chose :
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <MetricCard emphasis label="ROI capital">
                    <span className="num">bénéfice / capital total dépensé</span>
                    <p className="mt-1 text-[11px] text-ink-muted">
                      Ta ROI réelle. Si tu mets 1M et sors 1.2M, ROI = <span className="num">+20%</span>.
                      C'est celle qui pilote le tri des routes.
                    </p>
                  </MetricCard>
                  <MetricCard label="Marge efficacité (V1)">
                    <span className="num">bénéfice / (capital − récup)</span>
                    <p className="mt-1 text-[11px] text-ink-muted">
                      Mesure l'efficacité du process mais gonfle le %. Utile en secondaire, pas
                      pour arbitrer.
                    </p>
                  </MetricCard>
                </div>
              </Section>

              <Section icon={<ArrowRight className="h-4 w-4" />} title="Instant sell vs Sell order">
                <p>Deux façons de vendre ton stock, avec deux profils de risque :</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-fresh/30 bg-fresh/5 p-3">
                    <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-fresh">
                      Instant sell (safe)
                    </h4>
                    <p className="text-xs text-ink-muted">
                      Tu remplis le meilleur buy order existant. Silver <strong>immédiat</strong>,
                      taxe 8%. Zéro attente, aucun risque.
                    </p>
                  </div>
                  <div className="rounded-lg border border-primary-500/30 bg-primary-500/5 p-3">
                    <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary-300">
                      Sell order (attente)
                    </h4>
                    <p className="text-xs text-ink-muted">
                      Tu poses un ordre sous-coté. Revenu <strong>espéré</strong>, taxe 13%.
                      L'outil affiche une "fill proba" — sous 40%, c'est risqué.
                    </p>
                  </div>
                </div>
                <p className="mt-3 text-ink-muted">
                  L'outil te donne les deux, mais trie sur <strong>instant sell</strong> parce
                  que c'est le silver que ta banque verra à coup sûr.
                </p>
              </Section>

              <Section icon={<Timer className="h-4 w-4" />} title="Freshness — la data AODP et son gros piège">
                <p>
                  Les prix AODP viennent de joueurs qui{' '}
                  <strong>ont le client AODP installé et ouvrent leur panneau marché</strong>{' '}
                  en jeu. Sans le client, ouvrir le marché ne partage rien.
                </p>
                <Callout tone="hint">
                  <strong>Le vrai levier :</strong> installe le client AODP depuis{' '}
                  <span className="num">albion-online-data.com</span>, garde-le ouvert quand tu
                  joues, et pense à ouvrir les carnets de tes villes cibles avant de lancer
                  une analyse. C'est TA propre navigation qui alimente l'outil.
                </Callout>
                <p className="mt-3">Barème de confiance appliqué au revenu selon l'âge :</p>
                <div className="mt-2 space-y-1.5 text-xs text-ink-muted">
                  <p>
                    <span className="text-fresh">●</span> <strong>&lt; 30 min</strong> — facteur
                    1.00, aucune décote.
                  </p>
                  <p>
                    <span className="text-fresh">●</span> <strong>30 min - 1h</strong> — facteur
                    0.95.
                  </p>
                  <p>
                    <span className="text-caution">●</span> <strong>1h - 2h</strong> — facteur
                    0.85, la donnée bouge vite.
                  </p>
                  <p>
                    <span className="text-caution">●</span> <strong>2h - 4h</strong> — facteur
                    0.70, méfiance sérieuse.
                  </p>
                  <p>
                    <span className="text-critical">●</span> <strong>&gt; 4h</strong> — facteur
                    0.55 puis 0.40, quasi exclu.
                  </p>
                </div>
                <p className="mt-3 text-ink-muted">
                  Deux outils pour combattre le pb :
                </p>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-ink-muted">
                  <li>
                    La <strong>check-list fraîcheur</strong> à droite = les pages à ouvrir en
                    jeu (avec ton client AODP actif) pour actualiser la data.
                  </li>
                  <li>
                    Le bouton <strong>Rafraîchir</strong> en haut des résultats force l'outil à
                    contourner son cache interne (5 min) et re-questionner AODP tout de suite.
                  </li>
                </ul>
                <Callout tone="info">
                  <strong>Important :</strong> le coût d'achat affiché n'est pas décoté par la
                  freshness. Confirme toujours le prix au marché en jeu avant de dépenser gros
                  — si le carnet a bougé depuis la dernière upload, tu risques de payer plus.
                </Callout>
              </Section>

              <Section icon={<Wand2 className="h-4 w-4" />} title="Les enchantements (.1 à .4)">
                <p>
                  Chaque ressource existe en versions enchantées. La recette et le RRR sont
                  identiques ; seul l'item AODP change (T7_WOOD → T7_WOOD_LEVEL1@1).
                </p>
                <Callout tone="hint">
                  <strong>Pourquoi c'est intéressant :</strong> peu de refineurs touchent aux
                  enchants (barrière capital + focus), donc marchés moins saturés et marges
                  souvent nettement meilleures. En pratique, un T5 .1 wood peut donner +30% ROI
                  quand un T7 base est à -1%. Contrepartie : volumes 24h plus faibles, sell
                  orders plus difficiles à remplir.
                </Callout>
              </Section>

              <Section icon={<Info className="h-4 w-4" />} title="Par où commencer">
                <ol className="list-decimal space-y-2 pl-5 text-ink-muted">
                  <li>
                    <strong className="text-ink">Choisis une filière</strong> que tu peux
                    physiquement transporter (safe si tu débutes : reste en zone royale).
                  </li>
                  <li>
                    <strong className="text-ink">Mets ton capital réel</strong> en mode Capital
                    — l'outil calcule combien tu peux raffiner.
                  </li>
                  <li>
                    <strong className="text-ink">Active le focus</strong> si tu en as (bonus
                    RRR énorme, +59%).
                  </li>
                  <li>
                    <strong className="text-ink">Ouvre les pages de la check-list</strong> en
                    jeu avant de committer — un prix vieux fausse tout.
                  </li>
                  <li>
                    <strong className="text-ink">Reprends le prix top buy en jeu</strong> avant
                    l'instant sell. Il peut avoir bougé depuis la dernière minute.
                  </li>
                </ol>
                <p className="mt-3 text-ink-muted">
                  Petit bonus : sur les <strong>survole ?</strong> à côté des libellés dans
                  l'interface, tu retrouves la définition du terme concerné sans avoir à
                  ouvrir ce guide.
                </p>
              </Section>
            </div>

            <footer className="rounded-b-xl border-t border-surface-border/60 bg-surface-sunken/40 px-6 py-3 text-center text-xs text-ink-faint">
              Prêt·e à lancer ? Ferme ce panneau et attaque ta première optimisation.
            </footer>
          </motion.article>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

interface SectionProps {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}

const Section: FC<SectionProps> = ({ icon, title, children }) => (
  <section>
    <div className="mb-3 flex items-center gap-2">
      <span className="text-primary-400">{icon}</span>
      <h3 className="text-base font-semibold text-ink">{title}</h3>
    </div>
    <div className="pl-6">{children}</div>
  </section>
)

interface BadgedLineProps {
  badge: string
  title: string
  children: React.ReactNode
}

const BadgedLine: FC<BadgedLineProps> = ({ badge, title, children }) => (
  <div className="flex items-start gap-2">
    <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary-500/25 text-[10px] font-bold text-primary-300">
      {badge}
    </span>
    <div className="min-w-0">
      <span className="font-sans font-semibold text-ink">{title}</span>
      <span className="font-sans text-ink-muted"> — {children}</span>
    </div>
  </div>
)

interface MetricCardProps {
  label: string
  emphasis?: boolean
  children: React.ReactNode
}

const MetricCard: FC<MetricCardProps> = ({ label, emphasis, children }) => (
  <div
    className={
      emphasis
        ? 'rounded-lg border border-primary-500/40 bg-primary-500/5 p-3'
        : 'rounded-lg border border-surface-border/60 bg-surface/40 p-3'
    }
  >
    <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
      {label}
    </div>
    <div className="text-xs text-ink">{children}</div>
  </div>
)

interface CalloutProps {
  tone: 'info' | 'hint'
  children: React.ReactNode
}

const Callout: FC<CalloutProps> = ({ tone, children }) => {
  const styles =
    tone === 'info'
      ? 'border-primary-500/30 bg-primary-500/5 text-ink'
      : 'border-caution/30 bg-caution/5 text-ink'
  return (
    <div className={`mt-3 rounded-lg border ${styles} px-3 py-2 text-xs`}>
      {children}
    </div>
  )
}

export default HowItWorksModal
