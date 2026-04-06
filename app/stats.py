import sqlite3
from typing import Dict, Any, List
from app import logger

def get_aggregate_stats() -> Dict[str, Any]:
    with sqlite3.connect(logger._DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Total metrics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_requests,
                SUM(total_tokens) as total_tokens,
                AVG(duration_ms) as avg_duration_ms
            FROM logs
        """)
        totals = dict(cursor.fetchone())
        
        # Handle cases where there are no logs
        if totals["total_requests"] == 0:
            totals["total_tokens"] = 0
            totals["avg_duration_ms"] = 0.0
            
        # Model metrics
        cursor.execute("""
            SELECT 
                model_id,
                COUNT(*) as count
            FROM logs
            GROUP BY model_id
        """)
        totals["model_requests"] = [dict(row) for row in cursor.fetchall()]
        
        return totals

def get_recent_logs(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    with sqlite3.connect(logger._DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM logs 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]
