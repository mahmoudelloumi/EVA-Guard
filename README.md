# EVA-Guard

Détection et confirmation agentiques des attaques sur un nœud Ethereum.
Mini-projet — matière Blockchain.

## L'idée

- Le **ML** voit une anomalie : c'est une **alerte**, pas une preuve.
- Le **LLM + RAG** propose une explication (« c'est une Eclipse ? ») : c'est une **hypothèse**.
- Les **agents** mesurent des preuves dans plusieurs sources : P2P, chaîne, système, RPC.
- Une **règle fixe** décide : CONFIRMÉE si au moins 3 preuves vraies, venant d'au moins 2 sources,
  sur 2 fenêtres de suite. Sinon : NON CONFIRMÉE.

Le LLM propose et explique. Les outils mesurent. La règle décide.

## ⚠ Règle d'or (éthique)

Toutes les attaques tournent **uniquement** dans le réseau Docker isolé du labo.
Jamais sur mainnet, jamais sur un testnet public, jamais sur un nœud qui n'est pas à nous.

## Démarrage rapide

Il faut : Docker Desktop (avec WSL2) et Python 3.

```bash
python infra/setup.py
docker compose -f infra/docker-compose.yml up -d
python infra/check_network.py
```

Plus de détails : [infra/README.md](infra/README.md).

## Structure du repo

| Dossier | Contenu | Semaine |
|---|---|---|
| `infra/` | réseau Ethereum privé (Docker Compose, Clique), monitoring | 3–5 |
| `collector/` | collecteurs P2P, chaîne, système, proxy RPC | 4 |
| `traffic/` | générateur de trafic normal | 5 |
| `attacks/` | Eclipse, DoS P2P, RPC flood (option), anomalies bénignes | 6–8 |
| `data/` | dataset (fenêtres de 10 s) + labels + datasheet | 8 |
| `detection/` | features + modèles ML (Baseline 1) | 9–10 |
| `rag/` | corpus, playbooks, index (Baseline 2) | 11 |
| `agents/` | les 5 agents (LangGraph) | 11–13 |
| `dashboard/` | app Streamlit | 14 |
| `evaluation/` | expériences, métriques, ablation | 15 |
| `docs/` | cahier des charges, plan, schémas, rapport | — |

## Avancement

- [x] Semaine 3 : réseau privé Docker (signer + 4 honnêtes + victime), blocs toutes les 5 s
- [ ] Semaine 4 : Prometheus + Grafana + cAdvisor, collecteurs Python, format du dataset
- [ ] Semaine 5 : générateur de trafic, 2 h de baseline, squelette bout en bout
