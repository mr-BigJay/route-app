from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "route.db"


class DatabaseError(RuntimeError):
    """Raised when a database operation cannot be completed."""


class DatabaseManager:
    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(str(exc)) from exc
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS drivers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL UNIQUE,
                    first_name TEXT NOT NULL DEFAULT '',
                    last_name TEXT NOT NULL DEFAULT '',
                    mobile TEXT NOT NULL DEFAULT '',
                    national_id TEXT NOT NULL DEFAULT '',
                    birth_date TEXT NOT NULL DEFAULT '',
                    car_model TEXT NOT NULL DEFAULT '',
                    car_year TEXT NOT NULL DEFAULT '',
                    car_color TEXT NOT NULL DEFAULT '',
                    distance_rate REAL NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    FOREIGN KEY (category_id)
                        REFERENCES categories (id)
                        ON DELETE CASCADE,
                    UNIQUE (category_id, title)
                );

                CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    driver_id INTEGER,
                    vehicle TEXT NOT NULL,
                    mission_date TEXT NOT NULL,
                    mission_time TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    distance REAL NOT NULL DEFAULT 0,
                    passengers TEXT,
                    description TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (driver_id)
                        REFERENCES drivers (id)
                        ON DELETE SET NULL
                );
                """
            )
        self._ensure_driver_columns()
        self.seed_defaults()

    def _ensure_driver_columns(self) -> None:
        required_columns = {
            "first_name": "TEXT NOT NULL DEFAULT ''",
            "last_name": "TEXT NOT NULL DEFAULT ''",
            "mobile": "TEXT NOT NULL DEFAULT ''",
            "national_id": "TEXT NOT NULL DEFAULT ''",
            "birth_date": "TEXT NOT NULL DEFAULT ''",
            "car_model": "TEXT NOT NULL DEFAULT ''",
            "car_year": "TEXT NOT NULL DEFAULT ''",
            "car_color": "TEXT NOT NULL DEFAULT ''",
            "distance_rate": "REAL NOT NULL DEFAULT 0",
        }
        with self.connection() as conn:
            existing_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(drivers)").fetchall()
            }
            for column_name, definition in required_columns.items():
                if column_name not in existing_columns:
                    conn.execute(f"ALTER TABLE drivers ADD COLUMN {column_name} {definition}")

            rows = conn.execute(
                """
                SELECT id, full_name, first_name, last_name
                FROM drivers
                WHERE first_name = '' AND last_name = ''
                """
            ).fetchall()
            for row in rows:
                first_name, last_name = self._split_full_name(row["full_name"])
                conn.execute(
                    "UPDATE drivers SET first_name = ?, last_name = ? WHERE id = ?",
                    (first_name, last_name, row["id"]),
                )

    def seed_defaults(self) -> None:
        default_drivers = [
            {"first_name": "علی", "last_name": "محمدی"},
            {"first_name": "مهدی", "last_name": "احمدی"},
            {"first_name": "رضا", "last_name": "عباسی"},
            {"first_name": "حسن", "last_name": "رضایی"},
        ]
        default_categories = {
            "ستاد": ["شبکه بهداشت", "معاونت بهداشتی", "معاونت درمان"],
            "مرکز": ["مرکز کلاچای", "مرکز رحیم آباد", "مرکز واجارگاه"],
            "خانه بهداشت": ["زیاز", "جیرکلایه", "املش", "سفید آب"],
            "بیمارستان": ["بیمارستان رودسر"],
        }

        with self.connection() as conn:
            for driver in default_drivers:
                full_name = self._driver_full_name(driver)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO drivers (
                        full_name, first_name, last_name, mobile, national_id,
                        birth_date, car_model, car_year, car_color, distance_rate
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        full_name,
                        driver["first_name"],
                        driver["last_name"],
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        0,
                    ),
                )
            for category, locations in default_categories.items():
                cur = conn.execute(
                    "INSERT OR IGNORE INTO categories (title) VALUES (?)",
                    (category,),
                )
                category_id = cur.lastrowid
                if not category_id:
                    row = conn.execute(
                        "SELECT id FROM categories WHERE title = ?",
                        (category,),
                    ).fetchone()
                    category_id = int(row["id"])
                for title in locations:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO locations (category_id, title)
                        VALUES (?, ?)
                        """,
                        (category_id, title),
                    )

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        with self.connection() as conn:
            cur = conn.execute(query, params)
            return int(cur.lastrowid)

    def count(self, table_name: str) -> int:
        allowed_tables = {"drivers", "categories", "locations", "missions"}
        if table_name not in allowed_tables:
            raise ValueError("Invalid table name")
        row = self.fetch_one(f"SELECT COUNT(*) AS total FROM {table_name}")
        return int(row["total"]) if row else 0

    def list_drivers(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT id, full_name, first_name, last_name, mobile, national_id,
                   birth_date, car_model, car_year, car_color, distance_rate
            FROM drivers
            ORDER BY full_name
            """
        )

    def add_driver(self, data: dict[str, Any] | str) -> int:
        driver = self._normalize_driver_data(data)
        return self.execute(
            """
            INSERT INTO drivers (
                full_name, first_name, last_name, mobile, national_id,
                birth_date, car_model, car_year, car_color, distance_rate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                driver["full_name"],
                driver["first_name"],
                driver["last_name"],
                driver["mobile"],
                driver["national_id"],
                driver["birth_date"],
                driver["car_model"],
                driver["car_year"],
                driver["car_color"],
                float(driver["distance_rate"]),
            ),
        )

    def update_driver(self, driver_id: int, data: dict[str, Any] | str) -> None:
        driver = self._normalize_driver_data(data)
        self.execute(
            """
            UPDATE drivers
            SET full_name = ?, first_name = ?, last_name = ?, mobile = ?,
                national_id = ?, birth_date = ?, car_model = ?, car_year = ?,
                car_color = ?, distance_rate = ?
            WHERE id = ?
            """,
            (
                driver["full_name"],
                driver["first_name"],
                driver["last_name"],
                driver["mobile"],
                driver["national_id"],
                driver["birth_date"],
                driver["car_model"],
                driver["car_year"],
                driver["car_color"],
                float(driver["distance_rate"]),
                driver_id,
            ),
        )

    def delete_driver(self, driver_id: int) -> None:
        self.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))

    def _normalize_driver_data(self, data: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(data, str):
            first_name, last_name = self._split_full_name(data)
            data = {"first_name": first_name, "last_name": last_name}

        driver = {
            "first_name": str(data.get("first_name", "")).strip(),
            "last_name": str(data.get("last_name", "")).strip(),
            "mobile": str(data.get("mobile", "")).strip(),
            "national_id": str(data.get("national_id", "")).strip(),
            "birth_date": str(data.get("birth_date", "")).strip(),
            "car_model": str(data.get("car_model", "")).strip(),
            "car_year": str(data.get("car_year", "")).strip(),
            "car_color": str(data.get("car_color", "")).strip(),
            "distance_rate": float(data.get("distance_rate") or 0),
        }
        driver["full_name"] = self._driver_full_name(driver)
        return driver

    @staticmethod
    def _split_full_name(full_name: str) -> tuple[str, str]:
        parts = full_name.strip().split(maxsplit=1)
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], parts[1]

    @staticmethod
    def _driver_full_name(data: dict[str, Any]) -> str:
        return f"{data.get('first_name', '').strip()} {data.get('last_name', '').strip()}".strip()

    def list_categories(self) -> list[dict[str, Any]]:
        return self.fetch_all("SELECT id, title FROM categories ORDER BY title")

    def add_category(self, title: str) -> int:
        return self.execute(
            "INSERT INTO categories (title) VALUES (?)",
            (title.strip(),),
        )

    def update_category(self, category_id: int, title: str) -> None:
        self.execute(
            "UPDATE categories SET title = ? WHERE id = ?",
            (title.strip(), category_id),
        )

    def delete_category(self, category_id: int) -> None:
        self.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def list_locations(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT locations.id, locations.category_id, locations.title,
                   categories.title AS category_title
            FROM locations
            JOIN categories ON categories.id = locations.category_id
            ORDER BY categories.title, locations.title
            """
        )

    def add_location(self, category_id: int, title: str) -> int:
        return self.execute(
            "INSERT INTO locations (category_id, title) VALUES (?, ?)",
            (category_id, title.strip()),
        )

    def update_location(self, location_id: int, category_id: int, title: str) -> None:
        self.execute(
            "UPDATE locations SET category_id = ?, title = ? WHERE id = ?",
            (category_id, title.strip(), location_id),
        )

    def delete_location(self, location_id: int) -> None:
        self.execute("DELETE FROM locations WHERE id = ?", (location_id,))

    def list_missions(
        self,
        search: str = "",
        limit: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or {}
        clauses: list[str] = []
        params: list[Any] = []

        if search.strip():
            term = f"%{search.strip()}%"
            clauses.append(
                """
                (
                    drivers.full_name LIKE ?
                    OR missions.vehicle LIKE ?
                    OR missions.mission_date LIKE ?
                    OR missions.origin LIKE ?
                    OR missions.destination LIKE ?
                    OR missions.passengers LIKE ?
                    OR missions.description LIKE ?
                )
                """
            )
            params.extend([term] * 7)

        if filters.get("mission_date"):
            clauses.append("missions.mission_date = ?")
            params.append(filters["mission_date"])
        if filters.get("month"):
            clauses.append("missions.mission_date LIKE ?")
            params.append(f"{filters['month']}%")
        if filters.get("driver_id"):
            clauses.append("missions.driver_id = ?")
            params.append(filters["driver_id"])
        if filters.get("destination"):
            clauses.append("missions.destination = ?")
            params.append(filters["destination"])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_clause = "LIMIT ?" if limit is not None else ""
        if limit is not None:
            params.append(limit)

        return self.fetch_all(
            f"""
            SELECT missions.id, missions.driver_id, missions.vehicle,
                   missions.mission_date, missions.mission_time,
                   missions.origin, missions.destination, missions.distance,
                   missions.passengers, missions.description,
                   COALESCE(drivers.full_name, 'حذف شده') AS driver_name
            FROM missions
            LEFT JOIN drivers ON drivers.id = missions.driver_id
            {where}
            ORDER BY missions.mission_date DESC, missions.mission_time DESC, missions.id DESC
            {limit_clause}
            """,
            tuple(params),
        )

    def add_mission(self, data: dict[str, Any]) -> int:
        return self.execute(
            """
            INSERT INTO missions (
                driver_id, vehicle, mission_date, mission_time, origin,
                destination, distance, passengers, description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["driver_id"],
                data["vehicle"].strip(),
                data["mission_date"].strip(),
                data["mission_time"].strip(),
                data["origin"].strip(),
                data["destination"].strip(),
                float(data["distance"]),
                data.get("passengers", "").strip(),
                data.get("description", "").strip(),
            ),
        )

    def update_mission(self, mission_id: int, data: dict[str, Any]) -> None:
        self.execute(
            """
            UPDATE missions
            SET driver_id = ?, vehicle = ?, mission_date = ?, mission_time = ?,
                origin = ?, destination = ?, distance = ?, passengers = ?,
                description = ?
            WHERE id = ?
            """,
            (
                data["driver_id"],
                data["vehicle"].strip(),
                data["mission_date"].strip(),
                data["mission_time"].strip(),
                data["origin"].strip(),
                data["destination"].strip(),
                float(data["distance"]),
                data.get("passengers", "").strip(),
                data.get("description", "").strip(),
                mission_id,
            ),
        )

    def delete_mission(self, mission_id: int) -> None:
        self.execute("DELETE FROM missions WHERE id = ?", (mission_id,))

    def dashboard_stats(self, today: str) -> dict[str, int]:
        today_row = self.fetch_one(
            "SELECT COUNT(*) AS total FROM missions WHERE mission_date = ?",
            (today,),
        )
        return {
            "drivers": self.count("drivers"),
            "locations": self.count("locations"),
            "today_missions": int(today_row["total"]) if today_row else 0,
            "missions": self.count("missions"),
        }

    def report_totals(self, filters: dict[str, Any] | None = None) -> dict[str, float]:
        missions = self.list_missions(filters=filters)
        total_distance = sum(float(item["distance"] or 0) for item in missions)
        return {
            "missions": len(missions),
            "distance": total_distance,
        }
