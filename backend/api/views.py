import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .services.db_service import query_properties, get_property_stats, calculate_results_stats
from .services.ai_service import get_ai_intent, get_simple_response
from .services.cache_service import CACHE

# Constants
REAL_ESTATE_KEYWORDS = ['apartment','villa','rent','buy','property','dubai','uae','bed','price','area','studio','townhouse','penthouse']

@require_http_methods(["GET"]) 
def hello(request):
    q = request.GET.get('q', 'hello')
    message = get_simple_response(q)
    return JsonResponse({"message": message})

@csrf_exempt
@require_http_methods(["POST"]) 
def intent(request):
    data = json.loads(request.body.decode('utf-8')) if request.body else {}
    text = (data.get('q','') or '').lower()
    is_real_estate = any(k in text for k in REAL_ESTATE_KEYWORDS)
    return JsonResponse({"isRealEstate": bool(is_real_estate)})

@csrf_exempt
@require_http_methods(["POST"]) 
def search(request):
    data = json.loads(request.body.decode('utf-8')) if request.body else {}
    q = data.get('q','')
    
    # Intent check (simple keyword check for the search endpoint)
    if not any(k in q.lower() for k in REAL_ESTATE_KEYWORDS):
        return JsonResponse({
            "message": "Sorry, I can only search for UAE real estate.",
            "results": []
        }, status=200)
    
    filters = data.get('filters') or {}
    # Legacy support for top-level keys
    for key in ['beds', 'maxPrice', 'minPrice', 'city', 'area', 'type']:
        if key in data and key not in filters:
            filters[key] = data[key]
            
    page = int(data.get('page', 1))
    page_size = int(data.get('pageSize', 20))
    
    cache_key = f"search_{json.dumps(filters, sort_keys=True)}_{page}"
    cached_results = CACHE.get(cache_key)
    
    if cached_results:
        return JsonResponse({
            "summary": f"Found {len(cached_results)} properties (cached)",
            "results": cached_results,
            "sources": ["Bayut", "Propertyfinder", "Propsearch"],
            "cached": True
        })
    
    try:
        db_data = query_properties(filters, page, page_size)
        results = db_data['results']
        CACHE.set(cache_key, results)
        
        summary = f"Found {len(results)} properties"
        if filters.get('city'): summary += f" in {filters['city']}"
        
        return JsonResponse({
            "summary": summary,
            "results": results,
            "sources": ["Bayut", "Propertyfinder", "Propsearch"],
            "page": page,
            "pageSize": page_size,
            "hasMore": len(results) == page_size,
            "cached": False
        })
    except Exception as e:
        return JsonResponse({"message": f"Search error: {str(e)}", "results": []}, status=500)

@csrf_exempt
@require_http_methods(["POST"]) 
def stats(request):
    data = json.loads(request.body.decode('utf-8')) if request.body else {}
    filters = {
        "area": data.get('area'),
        "city": data.get('city')
    }
    
    try:
        stats_data = get_property_stats(filters)
        return JsonResponse(stats_data)
    except Exception as e:
        return JsonResponse({"message": f"Stats error: {str(e)}"}, status=500)

def format_response(text, stats_data=None, count=0):
    if not text: return text
    if stats_data:
        text = text.replace("{avg_price}", f"AED {int(stats_data['prices']['avg']):,}")
        text = text.replace("{min_price}", f"AED {int(stats_data['prices']['min']):,}")
        text = text.replace("{max_price}", f"AED {int(stats_data['prices']['max']):,}")
        text = text.replace("{area}", str(stats_data.get('area', 'the area')))
    text = text.replace("{count}", str(count))
    return text

from django.http import StreamingHttpResponse
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

def chat_stream_generator(user_message, session_context, cache_key):
    """
    High-Speed Agentic Engine: Executes AI Intent planning, DB Search, and Narrative in parallel.
    """
    import time
    start_time = time.time()
    
    # 1. AI SEARCH ARCHITECT PHASE
    ai_output = get_ai_intent(user_message, session_context)
    intent_type = ai_output.get('type')
    thought = ai_output.get('thought', 'Analyzing request...')
    print(f"🧠 AI ARCHITECT: {thought}")
    
    if intent_type == 'error':
        yield f'data: {json.dumps({"response": ai_output.get("response"), "type": "error"})}\n\n'
        return

    # Yield the initial greeting/response from the AI while we fetch data
    if ai_output.get('response'):
        yield f'data: {json.dumps({"type": "text_chunk", "content": ai_output["response"] + " "})}\n\n'

    if intent_type in ['info', 'clarification']:
        yield f'data: {json.dumps({"type": "final", "done": True})}\n\n'
        return

    if intent_type == 'stats':
        from .services.db_service import get_property_stats
        from .services.ai_service import generate_stats_narrative
        
        # Stats logic remains similar but uses the new structured plan if available
        plan = ai_output.get('searchPlan', {}).get('primary', {})
        stats_data = get_property_stats(plan)
        narrative = generate_stats_narrative(user_message, stats_data, session_context)
        
        table_data = []
        if stats_data:
            breakdown = stats_data.get('city_breakdown', [])
            if breakdown:
                for b in breakdown:
                    table_data.append([b['name'], f"AED {int(b['avg']):,}", f"AED {int(b['min']):,}", f"AED {int(b['max']):,}"])
            else:
                table_data.append([stats_data.get('area', 'Selected'), f"AED {int(stats_data['prices']['avg']):,}", f"AED {int(stats_data['prices']['min']):,}", f"AED {int(stats_data['prices']['max']):,}"])
        
        yield f'data: {json.dumps({"type": "stats", "stats": stats_data, "response": narrative, "tableData": table_data, "tableTitle": "Market Comparison Matrix"})}\n\n'
        yield f'data: {json.dumps({"type": "final", "done": True})}\n\n'
        return

    # 2. PARALLEL SEARCH & NARRATIVE
    search_plan = ai_output.get('searchPlan', {})
    page = session_context.get('page', 1)
    seen_ids = session_context.get('seen_ids', [])
    
    # Execute the Search Plan
    db_future = executor.submit(query_properties, search_plan, page=page, page_size=10, seen_ids=seen_ids)
    
    # Tell UI we are searching
    yield f'data: {json.dumps({"type": "intent", "filters": search_plan.get("primary", {}), "processing": True})}\n\n'
    
    try:
        db_data = db_future.result(timeout=7)
        results = db_data['results']
        
        # 3. PUSH RESULTS IMMEDIATELY
        yield f'data: {json.dumps({"type": "results", "results": results, "isFallback": db_data["isFallback"]})}\n\n'
        
        # 4. STREAM ADVISORY NARRATIVE
        from .services.ai_service import stream_professional_response
        narrative_gen = stream_professional_response(
            user_message, 
            results, 
            search_plan.get('primary', {}), 
            db_data['isFallback'], 
            len(results) > 0, 
            session_context
        )
        
        for chunk in narrative_gen:
            yield f'data: {json.dumps({"type": "text_chunk", "content": chunk})}\n\n'
            
        # 5. FINAL METADATA
        table_data = []
        if ai_output.get('wantsTable') and results:
            for r in results[:10]:
                table_data.append([
                    r.get('beds', '-'),
                    f"{int(r['price']):,}",
                    r.get('location', '')[:30],
                    r.get('title', '')[:40] + '...'
                ])

        yield f'data: {json.dumps({"type": "final", "tableData": table_data, "tableTitle": "Property Summary:", "done": True})}\n\n'
        
    except Exception as e:
        yield f'data: {json.dumps({"response": f"System Speed Error: {str(e)}", "type": "error"})}\n\n'
        
    except Exception as e:
        yield f'data: {json.dumps({"response": f"System Speed Error: {str(e)}", "type": "error"})}\n\n'

@csrf_exempt
@require_http_methods(["POST"]) 
def chat(request):
    """Unified endpoint using the Hyper-Speed Parallel Engine"""
    data = json.loads(request.body.decode('utf-8')) if request.body else {}
    user_message = data.get('message', '').strip()
    session_context = data.get('context', {})
    
    if not user_message:
        return JsonResponse({"response": "How can I help you today?", "type": "info"})
    
    # SEMANTIC CACHE: Normalize message to increase hit rate
    norm_msg = user_message.lower().replace("?", "").replace("!", "").strip()
    norm_msg = norm_msg.replace("dubay", "dubai").replace("shrajh", "sharjah").replace("anjnm", "ajman")
    cache_key = f"chat_{norm_msg}_{json.dumps(session_context.get('filters', {}), sort_keys=True)}"
    
    # Note: For production streaming, use EventSource or fetch/stream on frontend
    response = StreamingHttpResponse(chat_stream_generator(user_message, session_context, cache_key), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response
            
    if intent_type == 'table':
        return JsonResponse({
            "response": ai_output.get('response'),
            "type": "table",
            "tableData": ai_output.get('tableData', []),
            "tableTitle": ai_output.get('tableTitle', 'Data Matrix'),
            "tableColumns": ai_output.get('tableColumns', ["Field", "Value"])
        })

    if intent_type == 'stats':
        filters = ai_output.get('filters', {})
        try:
            stats_data = get_property_stats(filters)
            
            # Use AI to narrate stats professionally
            from .services.ai_service import generate_stats_narrative
            response_text = generate_stats_narrative(user_message, stats_data, session_context)
            
            # Backend-generated Comparison Matrix for Stats
            table_data = []
            table_title = "Market Price Comparison"
            table_columns = ["City / Area", "Avg Rate", "Min Rate", "Max Rate"]

            if ai_output.get('wantsTable') and stats_data:
                breakdown = stats_data.get('city_breakdown', [])
                if breakdown:
                    # Multi-city comparison
                    for b in breakdown:
                        table_data.append([
                            b['name'],
                            f"AED {int(b['avg']):,}",
                            f"AED {int(b['min']):,}",
                            f"AED {int(b['max']):,}"
                        ])
                else:
                    # Single area comparison
                    table_data.append([
                        stats_data.get('area', 'Selected Area'),
                        f"AED {int(stats_data['prices']['avg']):,}",
                        f"AED {int(stats_data['prices']['min']):,}",
                        f"AED {int(stats_data['prices']['max']):,}"
                    ])
                
            return JsonResponse({
                "response": response_text,
                "type": "stats",
                "stats": stats_data,
                "tableData": table_data if table_data else None,
                "tableTitle": table_title,
                "tableColumns": table_columns
            })
        except Exception as e:
            return JsonResponse({"response": f"Stats Error: {str(e)}", "type": "error"})

    # ULTIMATE FALLBACK: If AI provided a response string, use it!
    if ai_output.get('response'):
        return JsonResponse({
            "response": format_response(ai_output.get('response')),
            "type": intent_type or "info"
        })

    return JsonResponse({"response": "I'm not sure how to help with that. Could you rephrase?", "type": "info"})

@csrf_exempt
@require_http_methods(["POST"])
def clear_cache(request):
    CACHE.clear()
    return JsonResponse({"status": "success", "message": "Cache cleared."})
