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
                    vehicle_status TEXT NOT NULL DEFAULT 'دولتی',
                    distance_rate REAL NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    inactive_reason TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL UNIQUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    is_locked INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
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
        self._ensure_category_location_columns()
        self.seed_defaults()

    def _ensure_category_location_columns(self) -> None:
        with self.connection() as conn:
            category_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(categories)").fetchall()
            }
            if "sort_order" not in category_columns:
                conn.execute("ALTER TABLE categories ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")
            if "is_locked" not in category_columns:
                conn.execute("ALTER TABLE categories ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 0")

            location_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(locations)").fetchall()
            }
            if "sort_order" not in location_columns:
                conn.execute("ALTER TABLE locations ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")

            conn.execute(
                """
                UPDATE categories
                SET title = 'مرکز درمانی'
                WHERE title = 'مرکز'
                  AND NOT EXISTS (SELECT 1 FROM categories WHERE title = 'مرکز درمانی')
                """
            )
            old_center = conn.execute(
                "SELECT id FROM categories WHERE title = 'مرکز'"
            ).fetchone()
            new_center = conn.execute(
                "SELECT id FROM categories WHERE title = 'مرکز درمانی'"
            ).fetchone()
            if old_center and new_center:
                old_id = int(old_center["id"])
                new_id = int(new_center["id"])
                old_locations = conn.execute(
                    "SELECT id, title FROM locations WHERE category_id = ?",
                    (old_id,),
                ).fetchall()
                for location in old_locations:
                    duplicate = conn.execute(
                        """
                        SELECT 1 FROM locations
                        WHERE category_id = ? AND title = ?
                        """,
                        (new_id, location["title"]),
                    ).fetchone()
                    if duplicate:
                        conn.execute("DELETE FROM locations WHERE id = ?", (location["id"],))
                    else:
                        conn.execute(
                            "UPDATE locations SET category_id = ? WHERE id = ?",
                            (new_id, location["id"]),
                        )
                conn.execute("DELETE FROM categories WHERE id = ?", (old_id,))

            permanent_categories = [
                (1, "ستاد"),
                (2, "بیمارستان"),
                (3, "مرکز درمانی"),
                (4, "خانه بهداشت"),
            ]
            for sort_order, title in permanent_categories:
                row = conn.execute(
                    "SELECT id FROM categories WHERE title = ?",
                    (title,),
                ).fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE categories
                        SET sort_order = ?, is_locked = 1
                        WHERE id = ?
                        """,
                        (sort_order, row["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO categories (title, sort_order, is_locked)
                        VALUES (?, ?, 1)
                        """,
                        (title, sort_order),
                    )

            rows = conn.execute(
                """
                SELECT id
                FROM categories
                WHERE sort_order = 0
                ORDER BY title
                """
            ).fetchall()
            next_order = 5
            for row in rows:
                conn.execute(
                    "UPDATE categories SET sort_order = ? WHERE id = ?",
                    (next_order, row["id"]),
                )
                next_order += 1

            location_rows = conn.execute(
                """
                SELECT id, category_id
                FROM locations
                WHERE sort_order = 0
                ORDER BY category_id, title
                """
            ).fetchall()
            per_category_count: dict[int, int] = {}
            for row in location_rows:
                category_id = int(row["category_id"])
                per_category_count[category_id] = per_category_count.get(category_id, 0) + 1
                conn.execute(
                    "UPDATE locations SET sort_order = ? WHERE id = ?",
                    (per_category_count[category_id], row["id"]),
                )

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
            "vehicle_status": "TEXT NOT NULL DEFAULT 'دولتی'",
            "distance_rate": "REAL NOT NULL DEFAULT 0",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "inactive_reason": "TEXT NOT NULL DEFAULT ''",
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
            "بیمارستان": ["بیمارستان رودسر"],
            "مرکز درمانی": ["مرکز کلاچای", "مرکز رحیم آباد", "مرکز واجارگاه"],
            "خانه بهداشت": ["زیاز", "جیرکلایه", "املش", "سفید آب"],
        }

        with self.connection() as conn:
            for driver in default_drivers:
                full_name = self._driver_full_name(driver)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO drivers (
                        full_name, first_name, last_name, mobile, national_id,
                        birth_date, car_model, car_year, car_color, distance_rate,
                        is_active, inactive_reason
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        1,
                        "",
                    ),
                )
            for category, locations in default_categories.items():
                conn.execute(
                    "INSERT OR IGNORE INTO categories (title) VALUES (?)",
                    (category,),
                )
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
                   birth_date, car_model, car_year, car_color, vehicle_status,
                   distance_rate, is_active, inactive_reason
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
                birth_date, car_model, car_year, car_color, vehicle_status,
                distance_rate, is_active, inactive_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                driver["vehicle_status"],
                float(driver["distance_rate"]),
                int(driver["is_active"]),
                driver["inactive_reason"],
            ),
        )

    def update_driver(self, driver_id: int, data: dict[str, Any] | str) -> None:
        driver = self._normalize_driver_data(data)
        self.execute(
            """
            UPDATE drivers
            SET full_name = ?, first_name = ?, last_name = ?, mobile = ?,
                national_id = ?, birth_date = ?, car_model = ?, car_year = ?,
                car_color = ?, vehicle_status = ?, distance_rate = ?, is_active = ?,
                inactive_reason = ?
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
                driver["vehicle_status"],
                float(driver["distance_rate"]),
                int(driver["is_active"]),
                driver["inactive_reason"],
                driver_id,
            ),
        )

    def delete_driver(self, driver_id: int) -> None:
        self.execute("DELETE FROM drivers WHERE id = ?", (driver_id,))

    def set_driver_active(
        self,
        driver_id: int,
        is_active: bool,
        inactive_reason: str = "",
    ) -> None:
        self.execute(
            """
            UPDATE drivers
            SET is_active = ?, inactive_reason = ?
            WHERE id = ?
            """,
            (1 if is_active else 0, "" if is_active else inactive_reason.strip(), driver_id),
        )

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
            "vehicle_status": str(data.get("vehicle_status", "دولتی")).strip() or "دولتی",
            "distance_rate": float(data.get("distance_rate") or 0),
            "is_active": int(data.get("is_active", 1)),
            "inactive_reason": str(data.get("inactive_reason", "")).strip(),
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
        return self.fetch_all(
            """
            SELECT id, title, sort_order, is_locked
            FROM categories
            ORDER BY sort_order, title
            """
        )

    def add_category(self, title: str, sort_order: int | None = None) -> int:
        if sort_order is None:
            row = self.fetch_one("SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM categories")
            sort_order = int(row["next_order"]) if row else 1
        return self.execute(
            "INSERT INTO categories (title, sort_order, is_locked) VALUES (?, ?, 0)",
            (title.strip(), sort_order),
        )

    def update_category(self, category_id: int, title: str, sort_order: int) -> None:
        self.execute(
            "UPDATE categories SET title = ?, sort_order = ? WHERE id = ?",
            (title.strip(), sort_order, category_id),
        )

    def delete_category(self, category_id: int) -> None:
        self.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def get_category(self, category_id: int) -> dict[str, Any] | None:
        return self.fetch_one(
            """
            SELECT id, title, sort_order, is_locked
            FROM categories
            WHERE id = ?
            """,
            (category_id,),
        )

    def category_location_counts(self) -> dict[str, int]:
        rows = self.fetch_all(
            """
            SELECT categories.title, COUNT(locations.id) AS total
            FROM categories
            LEFT JOIN locations ON locations.category_id = categories.id
            WHERE categories.title IN ('ستاد', 'بیمارستان', 'مرکز درمانی', 'خانه بهداشت')
            GROUP BY categories.id, categories.title, categories.sort_order
            ORDER BY categories.sort_order
            """
        )
        return {row["title"]: int(row["total"]) for row in rows}

    def list_locations(self) -> list[dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT locations.id, locations.category_id, locations.title,
                   locations.sort_order,
                   categories.title AS category_title,
                   categories.sort_order AS category_sort_order
            FROM locations
            JOIN categories ON categories.id = locations.category_id
            ORDER BY categories.sort_order, locations.sort_order, locations.title
            """
        )

    def add_location(self, category_id: int, title: str) -> int:
        return self.execute(
            """
            INSERT INTO locations (category_id, title, sort_order)
            VALUES (
                ?,
                ?,
                COALESCE((SELECT MAX(sort_order) + 1 FROM locations WHERE category_id = ?), 1)
            )
            """,
            (category_id, title.strip(), category_id),
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
                   COALESCE(drivers.full_name, 'حذف شده') AS driver_name,
                   COALESCE(drivers.distance_rate, 0) AS driver_distance_rate
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
