"""
Vérifie que le réseau privé EVA-Guard marche bien :
  1. la victime annonce le bon enode (celui calculé par setup.py) ;
  2. des blocs sont produits (1 bloc toutes les 5 s) ;
  3. la victime a la même hauteur que le nœud référence (retard de sync = 0) ;
  4. la victime est connectée aux nœuds honnêtes.

Usage : python infra/check_network.py
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

VICTIM_RPC = "http://127.0.0.1:8545"
REFERENCE_RPC = "http://127.0.0.1:8546"
NODES_FILE = Path(__file__).resolve().parent / "config" / "nodes.json"
WAIT_S = 12  # environ 2 blocs


def rpc(url, method, params=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.load(resp)
    if "error" in data:
        raise RuntimeError(f"{method} : {data['error']}")
    return data["result"]


def enode_pubkey(enode_url: str) -> str:
    return enode_url.split("enode://")[1].split("@")[0]


def main():
    nodes = json.loads(NODES_FILE.read_text(encoding="utf-8"))
    name_of = {n["enode_id"]: name for name, n in nodes.items()}
    problems = []

    def check(ok: bool, message: str):
        print(("[OK]       " if ok else "[PROBLÈME] ") + message)
        if not ok:
            problems.append(message)

    try:
        info = rpc(VICTIM_RPC, "admin_nodeInfo")
        start_victim = int(rpc(VICTIM_RPC, "eth_blockNumber"), 16)
        start_ref = int(rpc(REFERENCE_RPC, "eth_blockNumber"), 16)
    except OSError as e:
        sys.exit(f"ERREUR : pas de réponse RPC ({e}).\nLe réseau tourne ? docker compose -f infra/docker-compose.yml ps")

    check(
        enode_pubkey(info["enode"]) == nodes["victim"]["enode_id"] and "@172.28.0.100:" in info["enode"],
        f"enode de la victime : {info['enode'][:30]}...@{info['enode'].split('@')[1]}",
    )

    print(f"Attente de {WAIT_S} s pour voir les nouveaux blocs...")
    time.sleep(WAIT_S)
    end_victim = int(rpc(VICTIM_RPC, "eth_blockNumber"), 16)
    end_ref = int(rpc(REFERENCE_RPC, "eth_blockNumber"), 16)

    check(end_ref > start_ref, f"blocs produits : référence {start_ref} -> {end_ref} (+{end_ref - start_ref} en {WAIT_S} s)")
    lag = end_ref - end_victim
    check(lag <= 1, f"retard de sync de la victime : {lag} bloc(s) (victime {end_victim}, référence {end_ref})")

    peers = sorted(name_of.get(enode_pubkey(p["enode"]), "INCONNU") for p in rpc(VICTIM_RPC, "admin_peers"))
    honest = [p for p in peers if nodes.get(p, {}).get("role") == "honest"]
    check(len(honest) >= 3, f"pairs de la victime ({len(peers)}) : {', '.join(peers) or 'aucun'}")

    print()
    if problems:
        print(f"{len(problems)} problème(s). Regarde les logs : docker compose -f infra/docker-compose.yml logs --tail 50")
        sys.exit(1)
    print("Tout est bon : le réseau privé tourne.")


if __name__ == "__main__":
    main()
