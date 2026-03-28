import os
import sqlite3

DB_PATH = "data.db"


def init_db():
    """Ініціалізація бази даних (idempotent).
    Створює всі необхідні таблиці для логіки бота + NFT + маркетплейс.
    """
    need_init = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        # Покращує concurrency
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass

        # Увімкнути FK (на майбутнє, якщо захочеш FK-зв'язки)
        try:
            conn.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass

        cursor = conn.cursor()

        # Загальна таблиця json_data (використовується load_data/save_data)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS json_data (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

        # users (можна використовувати як альтернативу json_data)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            coins REAL DEFAULT 0,
            GGs REAL DEFAULT 0,
            lost_coins REAL DEFAULT 0,
            won_coins REAL DEFAULT 0,
            status INTEGER DEFAULT 0,
            checks TEXT DEFAULT '[]'
        )
        """)

        # bets (лог для ігор)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            bet_amount REAL,
            choice TEXT,
            outcome TEXT,
            win INTEGER,
            payout REAL,
            ts INTEGER DEFAULT (strftime('%s','now'))
        )
        """)

        # checks (глобальні чеки)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            code TEXT PRIMARY KEY,
            creator_id TEXT NOT NULL,
            per_user REAL NOT NULL,
            remaining INTEGER NOT NULL,
            claimed TEXT DEFAULT '[]',
            password TEXT DEFAULT NULL
        )
        """)

        # promos (промокоди)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS promos (
            name TEXT PRIMARY KEY,
            reward REAL NOT NULL,
            claimed TEXT DEFAULT '[]',
            remaining_activations INTEGER NOT NULL DEFAULT 0
        )
        """)

        # bank_deposits (банк без карток; тільки депозити)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            principal REAL NOT NULL,
            rate REAL NOT NULL,
            term_days INTEGER NOT NULL,
            opened_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            closed_at INTEGER
        )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_bank_deposits_user ON bank_deposits(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_bank_deposits_status ON bank_deposits(status)"
        )

        # exchange_orders (біржові ордери)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            order_type TEXT NOT NULL,
            price REAL NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # clans
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            coffres REAL DEFAULT 0,
            level INTEGER DEFAULT 1,
            rating INTEGER DEFAULT 0,
            members TEXT DEFAULT '[]',
            admins TEXT DEFAULT '[]',
            owner TEXT UNIQUE NOT NULL
        )
        """)

        # clan_requests
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clan_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            clan_name TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
        """)

        # --- NFT: колекції ---
        # Стільки полів, скільки зазвичай потрібно: id, name, price, total, sold, creator_id, description
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS nft_collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            description TEXT DEFAULT '',
            total INTEGER DEFAULT 1,
            sold INTEGER DEFAULT 0,
            creator_id TEXT DEFAULT NULL,
            image_url TEXT DEFAULT NULL,
            rarity TEXT DEFAULT 'common',
            animation_url TEXT DEFAULT NULL,
            metadata TEXT DEFAULT '{}'
        )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_nft_collections_name ON nft_collections(name)"
        )

        # --- NFT: основна таблиця ---
        # Додав collection_id та serial (використовуються при mint / list / buy)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS nfts (
            id TEXT PRIMARY KEY,               -- UUID або власний id
            collection_id INTEGER,             -- посилання на nft_collections.id (необов'язково)
            serial INTEGER DEFAULT 0,          -- серійний номер в межах колекції
            owner_id TEXT NOT NULL,            -- id власника
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',        -- JSON string
            image_url TEXT DEFAULT NULL,
            animation_url TEXT DEFAULT NULL,   -- Lottie / gif / mp4
            rarity TEXT DEFAULT 'common',      -- common/rare/epic/legendary
            for_sale INTEGER DEFAULT 0,        -- 0/1
            price REAL DEFAULT 0,              -- ціна коли виставлений на продаж
            minted_at INTEGER DEFAULT (strftime('%s','now'))
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nfts_owner ON nfts(owner_id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_nfts_collection ON nfts(collection_id)"
        )

        # Історія NFT (mint / transfer / sold / burn)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS nft_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nft_id TEXT NOT NULL,
            from_user TEXT,
            to_user TEXT,
            action TEXT NOT NULL, -- minted/transferred/sold/burned
            price REAL,
            ts INTEGER DEFAULT (strftime('%s','now'))
        )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_nft_history_nft ON nft_history(nft_id)"
        )

        # Маркетплейс / sales
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS nft_sales (
            sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
            nft_id TEXT NOT NULL UNIQUE,
            seller_id TEXT NOT NULL,
            price REAL NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sales_seller ON nft_sales(seller_id)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_nft ON nft_sales(nft_id)")

        # додаткові індекси (продуктивність)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bets_user ON bets(user_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banned (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                created_at INTEGER DEFAULT (strftime('%s','now')),
                duration INTEGER
            )
        """)

        cursor.execute("""
             CREATE TABLE IF NOT EXISTS admins (
                 user_id INTEGER PRIMARY KEY
             )
        """)

        conn.commit()
    finally:
        conn.close()

    print(
        "DB initialized (json_data, users, bets, checks, promos, bank_deposits, exchange_orders, clans, "
        "nft_collections, nfts, nft_history, nft_sales, banned, admins)"
    )


if __name__ == "__main__":
    init_db()
