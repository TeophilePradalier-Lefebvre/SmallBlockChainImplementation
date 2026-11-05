# Small Blockchain Implementation

Projet pédagogique dont le but était de **comprendre le fonctionnement d'une blockchain** en la reconstruisant pas à pas, de zéro, en Python : registre d'opérations, hachage, signatures, nœuds pair-à-pair, consensus.

Ce n'est pas une blockchain utilisable en production. Les clés et les hachages font 32 bits, tout est volontairement lisible et simple, et rien n'est sécurisé contre une attaque (voir [Limites](#limites)).

## Auteurs

- Nathan BOUDRY
- Téophile PRADALIER-LEFEBVRE
- Mishael Natth VISWANATHAN
- Aaron Rohit JEROLD

## Structure : chaque dossier est indépendant

Le projet est découpé en 7 dossiers, qui correspondent à des étapes successives (Lab 1 à Lab 6, puis une version « réelle »). **Chaque dossier est autonome** : il contient sa propre copie de `JChain.py` et de `JCrypto.py` (là où elles sont nécessaires), dans la version correspondant à son étape. Il n'y a aucune dépendance entre dossiers, on peut en ouvrir un seul, le copier ailleurs et le lancer tel quel.

C'est pour cela que `JChain.py` et `JCrypto.py` existent en plusieurs exemplaires **différents** : `JChain.py` s'enrichit d'un dossier à l'autre (signatures, blocs signés, `Stake`, etc.), il ne faut donc pas les mélanger.

| Dossier | Étape | Ce qu'on y apprend | Contenu |
|---|---|---|---|
| `Digital_ledgers/` | Lab 1 | Registre numérique : état, opérations `Transfer` et `Init`, application d'une liste d'opérations | `Digital_ledgers.ipynb`, `JChain.py` |
| `Hashed structures/` | Lab 2 | Fonction de hachage, blocs chaînés par leur hash, structure en graphe (DAG) | `Hashed_structures.ipynb`, `JChain.py` |
| `Signatures/` | Lab 3 | Signatures à courbe elliptique (Schnorr), opérations signées, clés autorisées (admin) | `Signatures.ipynb`, `JChain.py` |
| `Decentralization/` | Lab 4 | Un nœud P2P qui tourne en local, échange d'opérations et de blocs, synchronisation | `Node.py`, `JChain.py`, `JCrypto.py`, `README.md` |
| `Block validation/` | Lab 5 | Blocs signés (Proof-of-Authority), collisions partielles, Proof-of-Work, Proof-of-Stake | `Block validation.ipynb`, `JChain.py`, `JCrypto.py` |
| `Consensus/` | Lab 6 | Amélioration des nœuds : `max_peers`, détection de pairs morts, règle de la plus longue chaîne, synchronisation par différence | `Improved_nodes.ipynb`, `JChain.py`, `JCrypto.py` |
| `IRL_Implementation/` | Final | Version plus « réelle » d'un nœud configuré par fichier JSON, avec bloc genesis et moniteur | `Node.py`, `JChain.py`, `JCrypto.py`, `config.json` |

Les notebooks (`.ipynb`) se lisent comme un cours : consignes en Markdown, code et exemples dessous. Les dossiers avec un `Node.py` contiennent un nœud que l'on lance dans un terminal.

## Les briques utilisées

- **`JCrypto.py`** : hachage 32 bits (`simple_hash`, basé sur SHA-256 tronqué), courbe elliptique, génération de clés, signature et vérification (Schnorr).
- **`JChain.py`** : `State` (qui possède quoi), `Operation` et ses types, `Ledger` (liste d'opérations), `Block`, `Blockchain`.
- **`Node.py`** : un nœud pair-à-pair. Chaque nœud est à la fois client et serveur, garde sa propre copie de la chaîne et vérifie tout ce qu'il reçoit au lieu de faire confiance.

Types d'opérations selon les étapes : `Init` (créer une variable), `Transfer` (déplacer des jetons), `EnrolAdminKey` (ajouter un administrateur), `Snapshot`, et `Stake` (mise en jeu de jetons pour la Proof-of-Stake, dans `Consensus/`).

## Lancer les exemples

Python 3 suffit, aucun paquet externe n'est nécessaire.

**Notebooks** (`Digital_ledgers`, `Hashed structures`, `Signatures`, `Block validation`, `Consensus`) : ouvrir le `.ipynb` avec Jupyter ou VS Code, depuis le dossier concerné, pour que `import JChain, JCrypto` trouve les fichiers voisins.

**Nœud du Lab 4** (`Decentralization/`) : le premier argument est le port d'écoute, les suivants sont les ports de nœuds déjà lancés.

```
cd Decentralization
python Node.py 5001
python Node.py 5002 5001
python Node.py 5003 5002
```

Un terminal par nœud. Une fois lancés, on dispose de commandes comme `enrol`, `init`, `transfer`, `block`, `chain`, `state`, `compare` ou `sync`. Le détail complet (commandes, messages, règles de validation) est dans [`Decentralization/README.md`](Decentralization/README.md).

**Nœud « IRL »** (`IRL_Implementation/`) : le nœud se lance à partir d'un fichier de configuration.

```
cd IRL_Implementation
python Node.py config.json
```

Le `config.json` fourni est un **modèle** : les valeurs entre chevrons (`<private key (int)>`, `<IP:port (string)>`...) sont à remplacer par de vraies valeurs (clé privée, adresse d'écoute, adresse du moniteur, nombre maximum de pairs). Le bloc `genesis` décrit le premier bloc de la chaîne. Ce dossier utilise des f-strings avec guillemets imbriqués, il faut donc **Python 3.12 ou plus récent**. Tapez `help` dans le nœud pour voir les commandes disponibles (`add_peer`, `transfer`, `create_block`, `mempool`, `state`...).

## Limites

Le but était d'apprendre, pas de produire un système sûr :

- tout tourne en local, et la chaîne n'est pas sauvegardée sur disque ;
- clés et hachages sur 32 bits : faciles à casser, volontairement lisibles ;
- le consensus est simplifié (règle de la plus longue chaîne, PoA / PoW / PoS de démonstration).
