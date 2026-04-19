import sqlite3
import time
from typing import Dict, Any, List
from app import logger

def get_aggregate_stats(hours: int = None) -> Dict[str, Any]:
    with logger.get_db_connection(logger._DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        where_clause = ""
        params = []
        if hours:
            where_clause = "WHERE timestamp >= ?"
            params.append(time.time() - (hours * 3600))
            
        # Total metrics
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_requests,
                SUM(prompt_tokens) as total_input_tokens,
                SUM(completion_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(COALESCE(prompt_cached_tokens, 0) + COALESCE(cache_read_input_tokens, 0)) as total_cached_tokens,
                AVG(duration_ms) as avg_duration_ms,
                AVG(tokens_per_second) as avg_tokens_per_second
            FROM logs
            {where_clause}
        """, params)
        totals = dict(cursor.fetchone())
        
        # Handle cases where there are no logs
        if totals["total_requests"] == 0:
            totals["total_input_tokens"] = 0
            totals["total_output_tokens"] = 0
            totals["total_tokens"] = 0
            totals["total_cached_tokens"] = 0
            totals["avg_duration_ms"] = 0.0
            totals["avg_tokens_per_second"] = 0.0
            
        # Model metrics
        cursor.execute(f"""
            SELECT 
                model_id,
                COUNT(*) as count,
                SUM(prompt_tokens) as total_input_tokens,
                SUM(completion_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(COALESCE(prompt_cached_tokens, 0) + COALESCE(cache_read_input_tokens, 0)) as total_cached_tokens,
                AVG(duration_ms) as avg_duration_ms,
                AVG(tokens_per_second) as avg_tokens_per_second
            FROM logs
            {where_clause}
            GROUP BY model_id
            ORDER BY count DESC
        """, params)
        totals["model_requests"] = [dict(row) for row in cursor.fetchall()]
        
        return totals

def get_recent_logs(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    with logger.get_db_connection(logger._DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM logs 
            ORDER BY timestamp DESC 
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cursor.fetchall()]

def get_time_series_stats(period: str) -> List[Dict[str, Any]]:
    """
    Groups usage by time period.
    period: 'hour' (last 24h), 'day' (last 30d), 'month' (last 12m)
    """
    with logger.get_db_connection(logger._DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if period == "hour":
            # Last 24 hours
            since = time.time() - (24 * 3600)
            strftime_fmt = "%Y-%m-%d %H:00"
        elif period == "day":
            # Last 30 days
            since = time.time() - (30 * 24 * 3600)
            strftime_fmt = "%Y-%m-%d"
        elif period == "month":
            # Last 12 months
            since = time.time() - (365 * 24 * 3600)
            strftime_fmt = "%Y-%m"
        else:
            return []

        cursor.execute(f"""
            SELECT 
                strftime('{strftime_fmt}', datetime(timestamp, 'unixepoch', 'localtime')) as label,
                COUNT(*) as requests,
                SUM(total_tokens) as tokens,
                SUM(COALESCE(prompt_cached_tokens, 0) + COALESCE(cache_read_input_tokens, 0)) as cached_tokens
            FROM logs
            WHERE timestamp >= ?
            GROUP BY label
            ORDER BY label ASC
        """, (since,))
        
        return [dict(row) for row in cursor.fetchall()]
