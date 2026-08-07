"""
experiment_db.py - Extended SQLite database module for batch experiment logging.
Extends the existing db.py chat persistence with experiment-specific tables.
All experiment results are stored alongside the existing chat history.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_experiment_tables():
    """
    Extend the existing DB with experiment-specific tables.
    Safe to run multiple times — uses CREATE TABLE IF NOT EXISTS.
    """
    conn = get_connection()
    try:
        conn.executescript("""
            -- One row per individual inference call
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                algorithm TEXT NOT NULL,
                instance_id TEXT NOT NULL,
                instance_title TEXT NOT NULL,
                domain TEXT NOT NULL,
                persona TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT 'gpt1900-instruct-v3-sft',
                seed INTEGER NOT NULL,
                system_prompt TEXT NOT NULL,
                user_prompt TEXT NOT NULL,
                response TEXT,
                response_length INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                error TEXT,
                duration_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );

            -- Scores per experiment (one row per evaluator layer)
            CREATE TABLE IF NOT EXISTS scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL,
                layer TEXT NOT NULL,
                algorithm_identified TEXT,
                optimality_score INTEGER,
                leakage_score INTEGER,
                anachronism_count INTEGER,
                structural_pattern TEXT,
                optimality_delta REAL,
                terminates INTEGER,
                deterministic INTEGER,
                implicit_complexity TEXT,
                period_consistent INTEGER,
                notes TEXT,
                scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            );

            -- Batch run metadata
            CREATE TABLE IF NOT EXISTS batch_runs (
                id TEXT PRIMARY KEY,
                description TEXT,
                algorithms TEXT,
                personas TEXT,
                seeds TEXT,
                total_experiments INTEGER,
                completed INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_experiments_algorithm
                ON experiments(algorithm);
            CREATE INDEX IF NOT EXISTS idx_experiments_persona
                ON experiments(persona);
            CREATE INDEX IF NOT EXISTS idx_experiments_status
                ON experiments(status);
            CREATE INDEX IF NOT EXISTS idx_scores_experiment
                ON scores(experiment_id);
        """)
        conn.commit()
        print("Experiment tables initialized.")
    finally:
        conn.close()


# ─── Batch Run Operations ───

def create_batch_run(batch_id: str, description: str, algorithms: list,
                     personas: list, seeds: list, total: int) -> str:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO batch_runs
               (id, description, algorithms, personas, seeds, total_experiments)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (batch_id, description,
             json.dumps(algorithms), json.dumps(personas),
             json.dumps(seeds), total)
        )
        conn.commit()
        return batch_id
    finally:
        conn.close()


def update_batch_progress(batch_id: str, completed: int, failed: int):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE batch_runs
               SET completed = ?, failed = ?
               WHERE id = ?""",
            (completed, failed, batch_id)
        )
        conn.commit()
    finally:
        conn.close()


def complete_batch_run(batch_id: str):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE batch_runs
               SET status = 'completed', completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (batch_id,)
        )
        conn.commit()
    finally:
        conn.close()


def get_batch_run(batch_id: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM batch_runs WHERE id = ?", (batch_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ─── Experiment Operations ───

def create_experiment(exp_id: str, algorithm: str, instance_id: str,
                      instance_title: str, domain: str, persona: str,
                      model: str, seed: int, system_prompt: str,
                      user_prompt: str) -> str:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO experiments
               (id, algorithm, instance_id, instance_title, domain,
                persona, model, seed, system_prompt, user_prompt, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (exp_id, algorithm, instance_id, instance_title, domain,
             persona, model, seed, system_prompt, user_prompt)
        )
        conn.commit()
        return exp_id
    finally:
        conn.close()


def complete_experiment(exp_id: str, response: str, duration: float):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE experiments
               SET response = ?, response_length = ?, duration_seconds = ?,
                   status = 'completed', completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (response, len(response), duration, exp_id)
        )
        conn.commit()
    finally:
        conn.close()


def fail_experiment(exp_id: str, error: str):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE experiments
               SET status = 'failed', error = ?,
                   completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (error, exp_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_experiment(exp_id: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_experiments(algorithm: str = None, persona: str = None,
                    status: str = None) -> list:
    conn = get_connection()
    try:
        query = "SELECT * FROM experiments WHERE 1=1"
        params = []
        if algorithm:
            query += " AND algorithm = ?"
            params.append(algorithm)
        if persona:
            query += " AND persona = ?"
            params.append(persona)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ─── Score Operations ───

def add_score(experiment_id: str, layer: str, **kwargs) -> int:
    """
    Add an evaluation score for an experiment.
    layer: 'llm_judge' | 'cs_expert' | 'humanist' | 'researcher'
    kwargs: any scoring fields from the scores table
    """
    conn = get_connection()
    try:
        fields = ["experiment_id", "layer"]
        values = [experiment_id, layer]
        for key, val in kwargs.items():
            fields.append(key)
            values.append(val)

        placeholders = ", ".join(["?" for _ in values])
        field_names = ", ".join(fields)
        cursor = conn.execute(
            f"INSERT INTO scores ({field_names}) VALUES ({placeholders})",
            values
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_scores(experiment_id: str) -> list:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM scores WHERE experiment_id = ? ORDER BY scored_at ASC",
            (experiment_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ─── Analysis Queries ───

def get_summary_stats():
    """Return aggregate statistics across all experiments."""
    conn = get_connection()
    try:
        stats = {}

        # Completion rates
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
                AVG(duration_seconds) as avg_duration,
                AVG(response_length) as avg_length
            FROM experiments
        """).fetchone()
        stats["overall"] = dict(row)

        # By algorithm
        rows = conn.execute("""
            SELECT algorithm,
                   COUNT(*) as total,
                   SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
                   AVG(response_length) as avg_length
            FROM experiments
            GROUP BY algorithm
        """).fetchall()
        stats["by_algorithm"] = [dict(r) for r in rows]

        # By persona
        rows = conn.execute("""
            SELECT persona,
                   COUNT(*) as total,
                   AVG(response_length) as avg_length
            FROM experiments
            GROUP BY persona
        """).fetchall()
        stats["by_persona"] = [dict(r) for r in rows]

        return stats
    finally:
        conn.close()


def export_all_results(output_path: str = "experiment_results.json"):
    """Export all experiments and scores to a JSON file for analysis."""
    conn = get_connection()
    try:
        experiments = [dict(r) for r in conn.execute(
            "SELECT * FROM experiments ORDER BY algorithm, persona, seed"
        ).fetchall()]

        for exp in experiments:
            exp["scores"] = [dict(r) for r in conn.execute(
                "SELECT * FROM scores WHERE experiment_id = ?",
                (exp["id"],)
            ).fetchall()]

        with open(output_path, "w") as f:
            json.dump(experiments, f, indent=2, default=str)

        print(f"Exported {len(experiments)} experiments to {output_path}")
        return output_path
    finally:
        conn.close()


# Initialize tables on import
init_experiment_tables()
