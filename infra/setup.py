"""
Prépare le réseau Ethereum privé du labo EVA-Guard (à lancer une seule fois).

Ce script crée :
  - les comptes Ethereum (signer, trafic normal, attaquants) et leur keystore ;
  - la clé de chaque nœud (nodekey) et son enode ;
  - le fichier genesis.json (Clique = PoA, 1 bloc toutes les 5 s) ;
  - le fichier infra/.env lu par docker-compose.

Tout est écrit dans infra/config/. Ce dossier est ignoré par git (il contient des clés).

Usage :
    python infra/setup.py           # crée la config si elle n'existe pas encore
    python infra/setup.py --force   # efface et recrée tout

Seulement la bibliothèque standard de Python + Docker.
"""

import argparse
import json
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

# --- Paramètres du labo -------------------------------------------------------

GETH_IMAGE = "ethereum/client-go:v1.13.15"  # >= 1.14 ne produit plus de blocs en Clique
CHAIN_ID = 1337
BLOCK_PERIOD = 5  # secondes entre deux blocs
GAS_LIMIT = 30_000_000
BALANCE_WEI = 10**24  # 1 million d'ETH par compte pré-financé (labo seulement)

HONEST_SUBNET = "172.28.0.0/24"  # honest_net
ATTACK_SUBNET = "172.29.0.0/24"  # attack_net (semaine 6)

N_TRAFFIC_ACCOUNTS = 5  # générateur de trafic normal
N_ATTACKERS = 10  # nœuds Sybil (un compte par attaquant)

# nom du nœud -> (rôle, IP dans son réseau Docker)
NODES = {
    "signer": ("honest", "172.28.0.10"),  # produit les blocs + sert de bootnode
    "reference": ("honest", "172.28.0.11"),  # donne la "vraie" hauteur de chaîne
    "honest1": ("honest", "172.28.0.12"),
    "honest2": ("honest", "172.28.0.13"),
    "honest3": ("honest", "172.28.0.14"),
    "victim": ("victim", "172.28.0.100"),
}
for i in range(1, N_ATTACKERS + 1):
    NODES[f"attacker{i}"] = ("attacker", f"172.29.0.{10 + i}")

INFRA_DIR = Path(__file__).resolve().parent
CONFIG_DIR = INFRA_DIR / "config"
ENV_FILE = INFRA_DIR / ".env"

# --- secp256k1 : pour calculer l'enode à partir de la nodekey -------------------
# L'enode d'un nœud = sa clé publique (64 octets en hex). On la calcule ici pour
# connaître l'adresse du bootnode et la liste des pairs honnêtes AVANT le lancement.

_P = 2**256 - 2**32 - 977
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_G = (
    0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8,
)


def _point_add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0] and (a[1] + b[1]) % _P == 0:
        return None
    if a == b:
        lam = 3 * a[0] * a[0] * pow(2 * a[1], -1, _P) % _P
    else:
        lam = (b[1] - a[1]) * pow(b[0] - a[0], -1, _P) % _P
    x = (lam * lam - a[0] - b[0]) % _P
    return (x, (lam * (a[0] - x) - a[1]) % _P)


def public_key_hex(private_key_hex: str) -> str:
    k = int(private_key_hex, 16)
    result, addend = None, _G
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return f"{result[0]:064x}{result[1]:064x}"


def new_private_key_hex() -> str:
    while True:
        k = secrets.randbits(256)
        if 0 < k < _N:
            return f"{k:064x}"


# --- Étapes -------------------------------------------------------------------


def check_docker():
    try:
        subprocess.run(["docker", "version"], check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        sys.exit("ERREUR : Docker ne répond pas. Lance Docker Desktop puis réessaie.")


def create_node_keys():
    nodes = {}
    for name, (role, ip) in NODES.items():
        key = new_private_key_hex()
        node_dir = CONFIG_DIR / "nodes" / name
        node_dir.mkdir(parents=True)
        (node_dir / "nodekey").write_text(key, encoding="ascii")  # sans retour à la ligne
        pub = public_key_hex(key)
        nodes[name] = {"role": role, "ip": ip, "enode_id": pub, "enode": f"enode://{pub}@{ip}:30303"}
    (CONFIG_DIR / "nodes.json").write_text(json.dumps(nodes, indent=2), encoding="utf-8")
    return nodes


def create_accounts(count: int) -> list[str]:
    """Crée `count` comptes avec `geth account new` (dans un conteneur jetable)."""
    (CONFIG_DIR / "password.txt").write_text(secrets.token_urlsafe(24), encoding="ascii")
    loop = (
        f"for i in $(seq 1 {count}); do "
        "geth account new --lightkdf --keystore /config/keystore --password /config/password.txt; "
        "done"
    )
    out = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{CONFIG_DIR}:/config", "--entrypoint", "/bin/sh", GETH_IMAGE, "-c", loop],
        check=True,
        capture_output=True,
        text=True,
    )
    addresses = re.findall(r"Public address of the key:\s+(0x[0-9a-fA-F]{40})", out.stdout + out.stderr)
    if len(addresses) != count:
        sys.exit(f"ERREUR : {len(addresses)} comptes créés au lieu de {count}.\n{out.stdout}\n{out.stderr}")
    return addresses


def write_genesis(signer: str, funded: list[str]):
    genesis = {
        "config": {
            "chainId": CHAIN_ID,
            "homesteadBlock": 0,
            "eip150Block": 0,
            "eip155Block": 0,
            "eip158Block": 0,
            "byzantiumBlock": 0,
            "constantinopleBlock": 0,
            "petersburgBlock": 0,
            "istanbulBlock": 0,
            "berlinBlock": 0,
            "londonBlock": 0,
            "clique": {"period": BLOCK_PERIOD, "epoch": 30000},
        },
        "difficulty": "1",
        "gasLimit": str(GAS_LIMIT),
        # Clique : 32 octets vides + adresse du signer + 65 octets vides (signature)
        "extraData": "0x" + "00" * 32 + signer[2:].lower() + "00" * 65,
        "alloc": {addr[2:].lower(): {"balance": hex(BALANCE_WEI)} for addr in funded},
    }
    (CONFIG_DIR / "genesis.json").write_text(json.dumps(genesis, indent=2), encoding="utf-8")


def write_env(signer: str, bootnode_enode: str):
    ENV_FILE.write_text(
        "# Genere par infra/setup.py : ne pas modifier a la main\n"
        f"GETH_IMAGE={GETH_IMAGE}\n"
        f"NETWORK_ID={CHAIN_ID}\n"
        f"SIGNER_ADDRESS={signer}\n"
        f"BOOTNODE_ENODE={bootnode_enode}\n"
        f"NETRESTRICT={HONEST_SUBNET},{ATTACK_SUBNET}\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="Prépare la config du réseau Ethereum privé EVA-Guard.")
    parser.add_argument("--force", action="store_true", help="efface et recrée toute la config")
    args = parser.parse_args()

    if CONFIG_DIR.exists() or ENV_FILE.exists():
        if not args.force:
            print("La config existe déjà (infra/config/). Rien à faire.")
            print("Pour tout recréer : python infra/setup.py --force")
            return
        shutil.rmtree(CONFIG_DIR, ignore_errors=True)
        ENV_FILE.unlink(missing_ok=True)

    check_docker()
    CONFIG_DIR.mkdir()

    print("1/4 Clés des nœuds (nodekey + enode)...")
    nodes = create_node_keys()

    n_accounts = 1 + N_TRAFFIC_ACCOUNTS + N_ATTACKERS
    print(f"2/4 Comptes Ethereum ({n_accounts}) avec geth account new...")
    addresses = create_accounts(n_accounts)
    signer = addresses[0]
    traffic = addresses[1 : 1 + N_TRAFFIC_ACCOUNTS]
    attackers = addresses[1 + N_TRAFFIC_ACCOUNTS :]
    accounts = {"signer": signer, "traffic": traffic, "attackers": attackers}
    (CONFIG_DIR / "accounts.json").write_text(json.dumps(accounts, indent=2), encoding="utf-8")

    print("3/4 genesis.json (Clique, 1 bloc / 5 s)...")
    write_genesis(signer, addresses)

    print("4/4 infra/.env pour docker-compose...")
    write_env(signer, nodes["signer"]["enode"])

    print()
    print(f"OK. Signer : {signer}")
    print("Lance le réseau : docker compose -f infra/docker-compose.yml up -d")
    if args.force:
        print("ATTENTION : avec --force, efface aussi les anciennes chaînes : docker compose -f infra/docker-compose.yml down -v")


if __name__ == "__main__":
    main()
