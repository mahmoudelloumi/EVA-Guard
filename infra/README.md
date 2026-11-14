# infra — Réseau Ethereum privé du labo

Réseau Geth **v1.13.15** en **Clique** (PoA) : un seul nœud « signer » produit un bloc toutes les 5 s.
Pas de minage, pas de validateurs. Très léger et facile à contrôler.

> Pourquoi v1.13.15 ? Les versions ≥ 1.14 ne produisent plus de blocs en Clique.

## Les nœuds

| Nœud | Conteneur | IP (honest_net) | Ports sur ta machine | Rôle |
|---|---|---|---|---|
| signer | `eva-signer` | 172.28.0.10 | — | produit les blocs + bootnode |
| reference | `eva-reference` | 172.28.0.11 | RPC 8546, métriques 6061 | donne la « vraie » hauteur |
| honest1–3 | `eva-honest1..3` | 172.28.0.12–14 | — | nœuds honnêtes |
| victim | `eva-victim` | 172.28.0.100 | RPC 8545, métriques 6060 | nœud surveillé (`maxpeers = 10`) |

Les ports écoutent seulement sur `127.0.0.1` (pas visibles depuis le réseau Wi-Fi).
Sous-réseau prévu pour les attaquants (semaine 6) : `attack_net` = 172.29.0.0/24.

## Commandes utiles

Toutes les commandes se lancent depuis la racine du repo.

Première fois seulement (crée les clés, les comptes et le genesis dans `infra/config/`) :

```bash
python infra/setup.py
```

Lancer le réseau :

```bash
docker compose -f infra/docker-compose.yml up -d
```

Vérifier que tout marche (blocs, retard de sync, pairs de la victime) :

```bash
python infra/check_network.py
```

Voir les logs de la victime :

```bash
docker logs -f eva-victim
```

Ouvrir la console Geth de la victime (ex. `admin.peers`, `eth.blockNumber`) :

```bash
docker exec -it eva-victim geth attach /data/geth.ipc
```

Arrêter le réseau (la chaîne est gardée) :

```bash
docker compose -f infra/docker-compose.yml down
```

Tout remettre à zéro (efface les chaînes, puis nouvelles clés et nouveau genesis) :

```bash
docker compose -f infra/docker-compose.yml down -v
```

```bash
python infra/setup.py --force
```

## Fichiers générés par `setup.py` (ignorés par git)

| Fichier | Contenu |
|---|---|
| `config/genesis.json` | genesis Clique (chainId 1337), comptes pré-financés |
| `config/accounts.json` | adresses : `signer`, `traffic` (5), `attackers` (10) |
| `config/keystore/` + `config/password.txt` | clés privées chiffrées des comptes |
| `config/nodes.json` | nom → rôle, IP, enode de chaque nœud (utile pour « % de pairs honnêtes connus ») |
| `config/nodes/<nom>/nodekey` | clé P2P de chaque nœud |
| `.env` | variables lues par docker-compose |

⚠ Ce sont des clés de labo. Ne les utilise jamais sur un vrai réseau.
