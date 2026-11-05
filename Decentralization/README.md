# Lab 4 - Decentralization: a small P2P blockchain node

## Done by,

*   Nathan BOUDRY
*   Téophile PRADALIER-LEFEBVRE
*   Mishael Natth VISWANATHAN
*   Aaron Rohit JEROLD

`Node.py` is an interactive node that runs on localhost. Several nodes started on different ports form a small peer-to-peer network. They can find each other, keep their own copy of a blockchain, pass operations around, check them, put them in blocks and send those blocks to everyone else.

There is no server. Every node is client and server at the same time, and every node checks what it receives instead of trusting it.

Files:

- `Node.py`: the node and its terminal (this lab)
- `JChain.py`: operations, ledger, blocks, blockchain (from the previous lab, with a few fixes, see the end)
- `JCrypto.py`: hash, elliptic curve and Schnorr signatures (unchanged)

Everything must be in the same folder. Python 3.8 or newer, no extra packages.

## Starting nodes

```
python Node.py <port> [peer_port ...]
```

The first argument is the port this node listens on. The other ones are ports of nodes that are already running (always on localhost). Start them in this order, a node can only contact peers that are already up.

For a network of three nodes, one terminal each:

```
python Node.py 5001
python Node.py 5002 5001
python Node.py 5003 5002
```

Here node 3 only knows node 2 at the start. Node 1 learns about node 2 through its HELLO, and node 3 can find node 1 with `discover`.

## What a node keeps

| Attribute | What it is |
|---|---|
| `peers` | list of `("localhost", port)` it knows |
| `chain` | its own copy of the blockchain (list of blocks) |
| `pending` | operations received or created but not yet in a block |
| `private_key`, `public_key` | generated at startup, used to sign what the node creates |
| `lock` | the listening thread and the terminal both touch `chain` and `pending`, so they share a lock |

The state (who owns what) is not stored. It is recomputed from the whole chain each time it is needed (`current_state()`). It is a bit slower, but it can never get out of sync with the chain.

## Commands

### Network

| Command | What it does |
|---|---|
| `peers` | print the known peers |
| `discover` | ask all known peers for their own peer list, then say HELLO to the new ones |
| `connect <port>` | add a peer by hand (it has to be reachable) |
| `disconnect <port>` | remove a peer and send it a BYE |
| `test` | broadcast a test message |

### Looking at the chain

| Command | What it does |
|---|---|
| `chain` | print every block: hash, previous hash, operations |
| `state` | print the state computed from the chain |
| `pending` | print the operations waiting for a block |
| `keys` | print this node's public key |
| `check` | two checks on the local chain (see below) |
| `compare` | ask all peers for the hash of their last block and say if it matches ours |
| `sync [port]` | ask all peers (or one) for their whole chain, and take it if it is longer and valid |

`check` prints two lines. The first one is only the hashes (each block contains the hash of the previous one). The second one also replays every operation of every block, in order, to see if each was valid when it was added.

### Creating operations and blocks

`me` can be used instead of a key and means this node's public key. Numbers are read as integers, anything else as text.

| Command | What it does |
|---|---|
| `enrol [key]` | add an admin key (this node's key by default) |
| `init <name> <value>` | create a variable with a starting value. Needs an admin key |
| `transfer <source> <target> <amount>` | move tokens. The source has to be the key of the node that signs |
| `clean` | remove invalid operations from `pending` |
| `block` | clean `pending`, put what is left in a new block, add it to the chain and broadcast it |
| `exit` | quit |

If the arguments are wrong the node just prints `Arguments invalides` and keeps running.

## A first session

On node 1, create an admin key, a balance and a transfer (777 is just a made-up target name, `keys` gives the real key of any node).

```
> enrol
Operation emise : {'op_type': 'EnrolAdminKey', 'key': 396371459334389945}
> init me 100
Operation emise : {'op_type': 'Init', 'name': 396371459334389945, 'value': 100}
> transfer me 777 30
Operation emise : {'op_type': 'Transfer', 'source': 396371459334389945, 'target': 777, 'amount': 30}
```

Nodes 2 and 3 print `Operation recue : ...` and `pending` shows the three operations on both. Then, on any node:

```
> block
Bloc ajoute, hash terminal = 2793521785
```

The others print `Bloc recu et ajoute, hash terminal = 2793521785`. Then `compare`:

```
> compare
Mon hash terminal : 2793521785 (1 blocs)
Pair ('localhost', 5002) : hash=2793521785 (1 blocs) -> IDENTIQUE
```

Try also an operation that can't work, for example `transfer me 999 99999` (more than the balance). It is accepted in `pending` (nobody checks at that point), then `clean` or `block` throws it away with `Operation invalide retiree`.

The messages printed by the program are in French, without accents.

## Operations

Every operation has a `content` (what it does), the `public_key` of whoever signed it, and the `signature`. Three questions are asked before an operation is accepted (`is_valid`): is the signature correct, is this key allowed to do it, does it make sense in the current state.

| Operation | Content | Valid when |
|---|---|---|
| `EnrolAdminKey` | `key` | no admin exists yet, or it is signed by an admin; and the key is not already there |
| `Init` | `name`, `value` | signed by an admin; and `name` does not exist yet |
| `Transfer` | `source`, `target`, `amount` | signed by `source`; `amount` is positive; `source` exists and has enough |

The first `EnrolAdminKey` of a chain can be signed by anyone, since there is no admin yet. After that only admins can enrol others.

For a `Transfer` the source is a public key, so the variable holding someone's balance has to be named with that key. This is why the example uses `init me 100` first.

## How things move

```
operation  ->  pending (everywhere)  ->  clean  ->  block  ->  chain (everywhere)
```

1. A node creates and signs an operation, adds it to its `pending` and broadcasts it.
2. A node that receives an operation it doesn't know adds it to its `pending` and passes it on. If it already knows it, it stops. That is what prevents messages from going around forever. It also ignores operations already in its chain, so one cannot be replayed.
3. `clean` takes the state of the chain and goes through `pending` in order. Each valid operation is applied to the state before looking at the next one, because an operation can depend on the previous one (an `Init` followed by a `Transfer` from that variable). The others are removed.
4. `block` builds a block with what is left. The block contains the hash of the previous block (`None` for the first one), and is broadcast.
5. A node that receives a block checks that it follows its last block and that all its operations are valid in its own state. Only then does it add it, remove those operations from its `pending` and pass the block on. If the block doesn't follow its chain, the node asks the sender for the whole chain (`GET_CHAIN`).

Comparing two chains is only a matter of comparing the hash of the last block, as long as both chains pass `check`.

## Messages

Everything is JSON sent over TCP, one message per connection (the sender connects, sends and closes, the receiver reads until the end). That is why a request carries a `from` field: the answer is a new message sent to that address.

| Type | Fields | Meaning |
|---|---|---|
| `HELLO` | from | "I exist", the receiver adds the sender to its peers |
| `BYE` | from | the sender leaves, the receiver forgets it |
| `GET_PEERS` | from | send me your peers |
| `PEERS` | from, peers | answer to `GET_PEERS` |
| `GET_HASH` | from | send me the hash of your last block |
| `HASH` | from, hash, length | answer to `GET_HASH` |
| `OPERATION` | op | a new operation for your `pending` |
| `BLOCK` | from, block | a new block |
| `GET_CHAIN` | from | send me your whole chain |
| `CHAIN` | from, blocks | answer to `GET_CHAIN` |
| `TEST` | content | just prints |

JSON has no tuples, so addresses arrive as lists and are turned back into tuples. A message that can't be read (not JSON, unknown operation type...) is printed and ignored, the node keeps going.

## Changes made to `JChain.py`

The version given for the lab had a few problems that only show up once operations travel on the network:

- `OPERATION_TYPES` was indented inside the class `Snapshot`, so `operation_from_dict` could not find it.
- `Snapshot.apply` returned `self.state`, which does not exist. It now returns a copy of `self.content["state"]`.
- `Transfer` accepted negative amounts, which lets someone take tokens from the target. Amounts must now be strictly positive.
- New `Block.from_dict`, to rebuild a block that arrived as JSON.

## Limits

- Only localhost, and the addresses are never saved: restart a node and its chain is gone (it can get it back with `sync`).
- If two nodes build different blocks on the same height, each keeps its own, nothing decides between them. A longer valid chain does win. Real consensus is for the next course.
- `disconnect` is not final: `discover` can bring the peer back if someone else still knows it.
- Nothing here is secure. The keys and the hash are 32 bits, they are made to be readable, not to resist an attack.
- No `Snapshot` command. The operation exists in `JChain.py` but its state mixes text and integer keys, which does not serialize properly.