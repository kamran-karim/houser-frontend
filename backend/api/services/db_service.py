import sqlite3
import os
from pathlib import Path

# Database path - Resolved relative to this file
DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / 'houser.db'

def get_db_connection():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query, params=(), fetch_all=True):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch_all:
            return [dict(row) for row in cur.fetchall()]
        return dict(cur.fetchone()) if cur.rowcount > 0 else None
    finally:
        conn.close()

def query_properties(plan=None, page=1, page_size=10, seen_ids=None):
    """
    Executes a high-performance search based on the AI's Search Plan.
    """
    plan = plan or {}
    primary = plan.get('primary', {})
    fallback_info = plan.get('fallback', {})
    seen_ids = seen_ids or []
    
    def build_query(filters):
        query = """
            SELECT 
                p.id, p.title, p.description, p.location, p.price,
                p.bedrooms, p.bathrooms, p.property_type, p.status,
                p.built_status, p.source, p.source_url, p.thumbnail,
                c.name as city_name, a.name as area_name, cat.name as category_name
            FROM properties p
            LEFT JOIN cities c ON p.city_id = c.id
            LEFT JOIN areas a ON p.area_id = a.id
            LEFT JOIN categories cat ON p.category_id = cat.id
            WHERE p.status = 'active' AND p.price > 0
        """
        params = []
        
        if filters.get('category'):
            query += " AND LOWER(cat.name) = ?"
            params.append(filters['category'].lower())
        
        if filters.get('beds') is not None:
            query += " AND p.bedrooms = ?"
            params.append(str(filters['beds']))
        
        if filters.get('maxPrice'):
            query += " AND p.price <= ?"
            params.append(float(filters['maxPrice']))
        
        if filters.get('minPrice'):
            query += " AND p.price >= ?"
            params.append(float(filters['minPrice']))
        
        if filters.get('city'):
            query += " AND (LOWER(c.name) = ? OR LOWER(c.name) LIKE ?)"
            city_val = filters['city'].lower()
            params.append(city_val)
            params.append(f"%{city_val}")
        
        if filters.get('area'):
            query += " AND (LOWER(a.name) LIKE ? OR LOWER(p.location) LIKE ?)"
            area_val = f"%{filters['area'].lower()}%"
            params.append(area_val)
            params.append(area_val)

        p_type = (filters.get('propertyType') or filters.get('type', 'buy')).lower()
        if p_type == 'rent':
            query += " AND (p.property_type = 'rent' OR (p.property_type = 'buy' AND p.price < 200000))"
        else:
            query += " AND (p.property_type = 'buy' OR (p.property_type = 'rent' AND p.price > 2000000))"

        if filters.get('isResidential', True):
            query += " AND cat.name IN ('Apartment', 'Villa', 'Townhouse', 'Penthouse', 'Duplex', 'Compound', 'Bungalow', 'Hotel & Hotel Apartment')"
            
        if seen_ids:
            placeholders = ', '.join(['?'] * len(seen_ids))
            query += f" AND p.id NOT IN ({placeholders})"
            params.extend(seen_ids)
            
        return query, params

    # 1. PRIMARY SEARCH
    query, params = build_query(primary)
    query += " ORDER BY p.price ASC LIMIT ?"
    params.append(page_size)
    
    rows = execute_query(query, params)
    results_list = [{"row": r, "exact": True} for r in rows]
    
    # 2. STRATEGIC AI FALLBACK (If primary results are low)
    if len(results_list) < 5 and fallback_info.get('area'):
        fallback_filters = primary.copy()
        fallback_filters['area'] = fallback_info['area']
        
        f_query, f_params = build_query(fallback_filters)
        
        # Exclude what we already found
        found_ids = [r['row']['id'] for r in results_list] + seen_ids
        if found_ids:
            placeholders = ', '.join(['?'] * len(found_ids))
            f_query += f" AND p.id NOT IN ({placeholders})"
            f_params.extend(found_ids)
            
        f_query += " ORDER BY p.price ASC LIMIT ?"
        f_params.append(page_size - len(results_list))
        
        f_rows = execute_query(f_query, f_params)
        for r in f_rows:
            results_list.append({"row": r, "exact": False, "fallbackReason": fallback_info.get('reason')})

    # 3. GENERIC CITY FALLBACK (If still low)
    if len(results_list) < 3 and primary.get('city'):
        generic_filters = primary.copy()
        generic_filters.pop('area', None) # Remove area for generic city search
        
        g_query, g_params = build_query(generic_filters)
        found_ids = [r['row']['id'] for r in results_list] + seen_ids
        if found_ids:
            placeholders = ', '.join(['?'] * len(found_ids))
            g_query += f" AND p.id NOT IN ({placeholders})"
            g_params.extend(found_ids)
            
        g_query += " ORDER BY p.price ASC LIMIT ?"
        g_params.append(page_size - len(results_list))
        
        g_rows = execute_query(g_query, g_params)
        for r in g_rows:
            results_list.append({"row": r, "exact": False, "fallbackReason": f"More options in {primary['city']}"})

    # Process results with insights
    stats = get_property_stats({'city': primary.get('city'), 'area': primary.get('area')})
    avg_price = stats['prices']['avg'] if stats else 0

    final_results = []
    for item in results_list:
        row = item['row']
        price = float(row['price']) if row['price'] else 0
        insight = None
        if avg_price > 0 and price > 0 and item['exact']:
            diff = ((price - avg_price) / avg_price) * 100
            if diff < -15: insight = f"Great Deal: {abs(int(diff))}% below avg"
            elif diff > 15: insight = f"Premium: {int(diff)}% above avg"

        final_results.append({
            "id": row['id'],
            "title": row['title'] or 'Untitled',
            "description": row['description'] or "No description.",
            "location": row['location'] or row['area_name'] or row['city_name'] or 'Unknown',
            "price": price,
            "beds": "Studio" if str(row['bedrooms']) == '0' else (row['bedrooms'] if row['bedrooms'] and str(row['bedrooms']).lower() != 'none' else 'N/A'),
            "baths": row['bathrooms'] or 'N/A',
            "area": row['area_name'] or row['city_name'] or 'N/A',
            "city": row['city_name'] or 'N/A',
            "type": row['property_type'] or 'buy',
            "thumbnail": row['thumbnail'],
            "source": row['source'],
            "sourceUrl": row['source_url'],
            "priceInsight": insight,
            "isExactMatch": item['exact'],
            "fallbackReason": item.get('fallbackReason')
        })
    
    return {"results": final_results, "isFallback": any(not r['isExactMatch'] for r in final_results)}

    # Stats
    stats_filters = {'city': filters.get('city'), 'area': filters.get('area')}
    stats = get_property_stats(stats_filters)
    avg_price = stats['prices']['avg'] if stats else 0

    final_results = []
    for item in results_list:
        row = item['row']
        price = float(row['price']) if row['price'] else 0
        insight = None
        if avg_price > 0 and price > 0 and item['exact']:
            diff = ((price - avg_price) / avg_price) * 100
            if diff < -15: insight = f"Great Deal: {abs(int(diff))}% below avg"
            elif diff > 15: insight = f"Premium: {int(diff)}% above avg"

        final_results.append({
            "id": row['id'],
            "title": row['title'] or 'Untitled',
            "description": row['description'] or "No description.",
            "location": row['location'] or row['area_name'] or row['city_name'] or 'Unknown',
            "price": price,
            "beds": "Studio" if str(row['bedrooms']) == '0' else (row['bedrooms'] if row['bedrooms'] and str(row['bedrooms']).lower() != 'none' else 'N/A'),
            "baths": row['bathrooms'] or 'N/A',
            "area": row['area_name'] or row['city_name'] or 'N/A',
            "city": row['city_name'] or 'N/A',
            "type": row['property_type'] or 'buy',
            "thumbnail": row['thumbnail'],
            "source": row['source'],
            "sourceUrl": row['source_url'],
            "priceInsight": insight,
            "isExactMatch": item['exact']
        })
    
    return {"results": final_results, "isFallback": is_fallback, "isSupplemented": len(final_results) > len(rows)}

from .cache_service import CACHE

def calculate_results_stats(results, area_name="This Selection"):
    """Instantly calculates stats from the current result set in memory (Fastest)"""
    if not results:
        return None
        
    prices = [float(r['price']) for r in results if r.get('price')]
    if not prices:
        return None
        
    return {
        "area": area_name,
        "is_result_based": True,
        "counts": {
            "total": len(results),
            "active": len(results)
        },
        "prices": {
            "min": min(prices),
            "max": max(prices),
            "avg": sum(prices) / len(prices)
        }
    }

def get_property_stats(filters=None):
    filters = filters or {}
    
    # Try cache first
    cache_key = f"stats_{filters.get('city')}_{filters.get('area')}"
    cached_stats = CACHE.get(cache_key)
    if cached_stats:
        return cached_stats

    # Optimization: Use a faster join instead of subqueries in WHERE
    query = """
        SELECT 
            COUNT(*) as total,
            MIN(p.price) as min_price,
            MAX(p.price) as max_price,
            AVG(p.price) as avg_price,
            SUM(p.price) as total_valuation
        FROM properties p
        LEFT JOIN areas a ON p.area_id = a.id
        LEFT JOIN cities c ON p.city_id = c.id
        WHERE p.price > 0 AND p.status = 'active'
    """
    
    params = []
    
    if filters.get('area'):
        query += " AND (p.location LIKE ? OR a.name LIKE ?)"
        area_val = f"%{filters['area']}%"
        params.append(area_val)
        params.append(area_val)
    
    if filters.get('city'):
        query += " AND LOWER(c.name) = ?"
        params.append(filters['city'].lower())
    
    rows = execute_query(query, params)
    row = rows[0] if rows else {}
    
    if not row or not row.get('total'):
        return None

    result = {
        "area": filters.get('area') or filters.get('city') or "All UAE",
        "is_market_based": True,
        "counts": {
            "total": row.get('total', 0),
            "active": row.get('total', 0)
        },
        "prices": {
            "min": float(row.get('min_price')) if row.get('min_price') else 0,
            "max": float(row.get('max_price')) if row.get('max_price') else 0,
            "avg": float(row.get('avg_price')) if row.get('avg_price') else 0,
            "total_value": float(row.get('total_valuation')) if row.get('total_valuation') else 0
        }
    }

    # Add city breakdown if it's a UAE-wide request
    if not filters.get('city') and not filters.get('area'):
        city_breakdown_query = """
            SELECT c.name, COUNT(*) as count, AVG(p.price) as avg_price, MIN(p.price) as min_price, MAX(p.price) as max_price
            FROM properties p
            JOIN cities c ON p.city_id = c.id
            WHERE p.status = 'active' AND p.price > 0
            GROUP BY c.name
            ORDER BY count DESC
            LIMIT 5
        """
        breakdown_rows = execute_query(city_breakdown_query)
        result["city_breakdown"] = [
            {
                "name": r['name'], 
                "count": r['count'], 
                "avg": r['avg_price'], 
                "min": r['min_price'],
                "max": r['max_price']
            } 
            for r in breakdown_rows
        ]
    
    CACHE.set(cache_key, result, ttl=3600)
    return result
