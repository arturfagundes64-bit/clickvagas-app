import sqlite3

from auth import hash_password


class SQLiteDatabase:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                account_type TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS parking_slots (
                number INTEGER PRIMARY KEY,
                slot_type TEXT NOT NULL DEFAULT 'carro'
            );
            CREATE TABLE IF NOT EXISTS vehicles (
                slot_number INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                model TEXT NOT NULL,
                plate TEXT NOT NULL UNIQUE,
                entry_at TEXT,
                vehicle_type TEXT NOT NULL DEFAULT 'carro',
                FOREIGN KEY (slot_number) REFERENCES parking_slots(number),
                FOREIGN KEY (username) REFERENCES users(username)
            );
            CREATE TABLE IF NOT EXISTS parking_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                slot_number INTEGER NOT NULL,
                username TEXT NOT NULL,
                model TEXT NOT NULL,
                vehicle_type TEXT NOT NULL DEFAULT 'carro',
                plate TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT ''
            );
            """
        )
        self._migrate_users_table()
        self._migrate_vehicles_table()
        self._migrate_slots_table()
        self._migrate_events_table()
        self.connection.commit()

    def _migrate_users_table(self):
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email" not in columns:
            self.connection.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
        if "phone" not in columns:
            self.connection.execute("ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''")

    def _migrate_vehicles_table(self):
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(vehicles)").fetchall()
        }
        if "vehicle_type" not in columns:
            self.connection.execute(
                "ALTER TABLE vehicles ADD COLUMN vehicle_type TEXT NOT NULL DEFAULT 'carro'"
            )

    def _migrate_slots_table(self):
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(parking_slots)").fetchall()
        }
        if "slot_type" not in columns:
            self.connection.execute(
                "ALTER TABLE parking_slots ADD COLUMN slot_type TEXT NOT NULL DEFAULT 'carro'"
            )
            self.connection.execute(
                "UPDATE parking_slots SET slot_type = COALESCE(("
                "SELECT vehicle_type FROM vehicles WHERE vehicles.slot_number = parking_slots.number"
                "), 'carro')"
            )

    def _migrate_events_table(self):
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(parking_events)").fetchall()
        }
        if "payment_method" not in columns:
            self.connection.execute(
                "ALTER TABLE parking_events ADD COLUMN payment_method TEXT NOT NULL DEFAULT ''"
            )

    def load_state(self):
        user_rows = self.connection.execute(
            "SELECT username, password_hash, account_type, email, phone FROM users ORDER BY username"
        ).fetchall()
        if not user_rows:
            has_saved_state = self.connection.execute(
                "SELECT 1 FROM parking_slots LIMIT 1"
            ).fetchone()
            if not has_saved_state:
                return None

        usuarios = {
            row["username"]: {
                "senha": row["password_hash"],
                "tipo": row["account_type"],
                "email": row["email"] or "",
                "telefone": row["phone"] or "",
                "veiculos": [],
            }
            for row in user_rows
        }
        slot_rows = self.connection.execute(
            "SELECT number, slot_type FROM parking_slots ORDER BY number"
        ).fetchall()
        vagas = [
            {
                "numero": row["number"],
                "status": "livre",
                "modelo": None,
                "placa": None,
                "usuario": None,
                "entrada": None,
                "tipo_veiculo": None,
                "tipo_vaga": row["slot_type"] or "carro",
            }
            for row in slot_rows
        ]
        vagas_por_numero = {vaga["numero"]: vaga for vaga in vagas}
        vehicle_rows = self.connection.execute(
            "SELECT slot_number, username, model, plate, entry_at, vehicle_type "
            "FROM vehicles ORDER BY slot_number"
        ).fetchall()
        for row in vehicle_rows:
            vaga = vagas_por_numero.get(row["slot_number"])
            if not vaga or row["username"] not in usuarios:
                continue
            tipo = row["vehicle_type"] or "carro"
            vaga.update(
                {
                    "status": "ocupado",
                    "modelo": row["model"],
                    "placa": row["plate"],
                    "usuario": row["username"],
                    "entrada": row["entry_at"],
                    "tipo_veiculo": tipo,
                }
            )
            usuarios[row["username"]]["veiculos"].append(
                {
                    "modelo": row["model"],
                    "placa": row["plate"],
                    "vaga": row["slot_number"],
                    "tipo_veiculo": tipo,
                }
            )
        eventos = [
            {
                "tipo": row["event_type"],
                "vaga": row["slot_number"],
                "usuario": row["username"],
                "modelo": row["model"],
                "tipo_veiculo": row["vehicle_type"] or "carro",
                "placa": row["plate"],
                "horario": row["occurred_at"],
                "valor": row["amount"],
                "forma_pagamento": row["payment_method"] or "",
            }
            for row in self.connection.execute(
                "SELECT event_type, slot_number, username, model, vehicle_type, plate, occurred_at, amount, payment_method "
                "FROM parking_events ORDER BY id"
            ).fetchall()
        ]
        return {"usuarios": usuarios, "vagas": vagas, "eventos": eventos}

    def save_state(self, state):
        usuarios = state.get("usuarios", {})
        vagas = state.get("vagas", [])
        eventos = state.get("eventos", [])
        with self.connection:
            self.connection.execute("DELETE FROM vehicles")
            if vagas:
                self.connection.executemany(
                    """
                    INSERT INTO parking_slots(number, slot_type) VALUES (?, ?)
                    ON CONFLICT(number) DO UPDATE SET slot_type=excluded.slot_type
                    """,
                    [
                        (vaga["numero"], vaga.get("tipo_vaga", "carro"))
                        for vaga in vagas
                    ],
                )
                numeros = [vaga["numero"] for vaga in vagas]
                placeholders_vagas = ",".join("?" for _ in numeros)
                self.connection.execute(
                    f"DELETE FROM parking_slots WHERE number NOT IN ({placeholders_vagas})",
                    tuple(numeros),
                )
            else:
                self.connection.execute("DELETE FROM parking_slots")
            if usuarios:
                placeholders = ",".join("?" for _ in usuarios)
                self.connection.execute(
                    f"DELETE FROM users WHERE username NOT IN ({placeholders})",
                    tuple(usuarios),
                )
            else:
                self.connection.execute("DELETE FROM users")

            user_rows = []
            for username, user in usuarios.items():
                user["senha"] = hash_password(user.get("senha", ""))
                user_rows.append(
                    (
                        username,
                        user["senha"],
                        user.get("tipo", "cliente"),
                        user.get("email", ""),
                        user.get("telefone", ""),
                    )
                )
            self.connection.executemany(
                """
                INSERT INTO users(username, password_hash, account_type, email, phone)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    account_type=excluded.account_type,
                    email=excluded.email,
                    phone=excluded.phone
                """,
                user_rows,
            )
            vehicle_rows = [
                (
                    vaga["numero"],
                    vaga["usuario"],
                    vaga["modelo"],
                    vaga["placa"],
                    vaga.get("entrada"),
                    vaga.get("tipo_veiculo") or "carro",
                )
                for vaga in vagas
                if vaga.get("status") == "ocupado"
                and vaga.get("usuario") in usuarios
                and vaga.get("modelo")
                and vaga.get("placa")
            ]
            self.connection.executemany(
                """
                INSERT INTO vehicles(slot_number, username, model, plate, entry_at, vehicle_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                vehicle_rows,
            )
            self.connection.execute("DELETE FROM parking_events")
            event_rows = [
                (
                    event.get("tipo", "entrada"),
                    event.get("vaga", 0),
                    event.get("usuario", ""),
                    event.get("modelo", ""),
                    event.get("tipo_veiculo") or "carro",
                    event.get("placa", ""),
                    event.get("horario", ""),
                    float(event.get("valor", 0) or 0),
                    event.get("forma_pagamento", ""),
                )
                for event in eventos
            ]
            self.connection.executemany(
                """
                INSERT INTO parking_events(
                    event_type, slot_number, username, model, vehicle_type, plate, occurred_at, amount, payment_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                event_rows,
            )
