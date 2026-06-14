================================================================
 M.A.D.E. COIN NODE  v0.9.1-testnet
 Making A Daily Earning
================================================================

QUICK START
-----------

Windows:
  1. Double-click start.bat
  2. Wait for dependencies to install (first run only)
  3. Your wallet address will be shown
  4. Type 'm' to start mining

Linux / macOS:
  1. Open a terminal in this folder
  2. Run:  bash start.sh
  3. Your wallet address will be shown
  4. Type 'm' to start mining

REQUIREMENTS
------------
  - Python 3.8 or higher
  - Internet connection (for P2P and dependencies)

  Windows users: Download Python from https://python.org
  Make sure to check "Add Python to PATH" during install!

FILES INSTALLED
---------------
  - node.py         Main entry point
  - blockchain.py   Blockchain core (blocks, PoW, transactions)
  - wallet.py       Wallet (ECDSA keys, signing)
  - miner.py        CPU mining engine
  - p2p.py          Peer-to-peer networking
  - api.py          REST API (port 7777)
  - requirements.txt Python dependencies

YOUR WALLET
-----------
  Your wallet is auto-created on first run and saved to:
    Windows:  C:\Users\<you>\.madecoin\wallet.json
    Linux:    ~/.madecoin/wallet.json
    macOS:    ~/.madecoin/wallet.json

  *** BACK UP wallet.json — losing it means losing your coins! ***

  Your wallet.json contains your private key. Never share it.

BLOCKCHAIN DATA
---------------
  Saved to ~/.madecoin/blockchain.json
  This file grows as you sync more blocks.

NODE COMMANDS (inside the node)
--------------------------------
  m / mine         Start CPU mining
  s / stop         Stop mining
  b / balance      Show your MADE balance
  i / info         Node info (height, hashrate, difficulty...)
  send <addr> <n>  Send MADE to an address
  peer <host:port> Connect to a peer
  peers            List connected peers
  verify           Check chain integrity
  q / quit         Save and exit
  help             Show all commands

REST API (runs on http://localhost:7777)
-----------------------------------------
  GET  /api/info              Node status
  GET  /api/blocks            Recent blocks
  GET  /api/block/<n>         Block by height or hash
  GET  /api/address/<addr>    Balance + tx history
  GET  /api/mempool           Pending transactions
  POST /api/transaction       Submit a signed transaction
  GET  /api/mining/status     Mining status + hashrate
  POST /api/mining/start      Start mining via API
  POST /api/mining/stop       Stop mining via API
  GET  /api/wallet            Your wallet address + balance
  POST /api/send              Send MADE from your wallet
  GET  /api/peers             List peers
  POST /api/peers             Add a peer

COMMAND LINE OPTIONS
--------------------
  python node.py --mine           Start mining on launch
  python node.py --peer HOST:PORT Connect to a specific peer
  python node.py --wallet-info    Show wallet address and exit
  python node.py --balance        Show balance and exit
  python node.py --no-api         Disable REST API
  python node.py --no-p2p         Disable P2P networking
  python node.py --api-port 8000  Use a different API port
  python node.py --p2p-port 19334 Use a different P2P port

TESTNET NOTES
-------------
  - This is TESTNET software — coins have no real value yet
  - Mainnet launch is in Phase 4 of the roadmap
  - Report bugs to: madecoin.io (contact page)

TECH SPECS
----------
  Algorithm:    SHA-256 Proof-of-Work
  Block time:   60 seconds
  Block reward: 5 MADE
  Max supply:   100,000,000 MADE
  Halving:      Every 2,100,000 blocks (~4 years)
  P2P port:     19333
  API port:     7777

================================================================
 M.A.D.E. Foundation | Mine It. Earn It. Build It.
================================================================
