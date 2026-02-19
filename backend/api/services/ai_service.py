import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

def get_client():
    global OPENAI_CLIENT, OPENAI_AVAILABLE
    if OPENAI_CLIENT:
        return OPENAI_CLIENT
        
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        OPENAI_AVAILABLE = False
        return None
        
    try:
        OPENAI_CLIENT = OpenAI(api_key=api_key)
        OPENAI_AVAILABLE = True
        return OPENAI_CLIENT
    except Exception as e:
        logger.error(f"OpenAI initialization failed: {str(e)}")
        OPENAI_AVAILABLE = False
        return None

# Initial check
OPENAI_CLIENT = None
OPENAI_AVAILABLE = True
get_client()

SYSTEM_PROMPT = """You are the Lead Search Architect at Houser AI, an elite UAE real estate advisory.
Your goal is to translate user requests into a high-performance "Search Plan".

### SEARCH ARCHITECTURE PRINCIPLES:
1. **Intelligence over Rigidness**: If a user asks for "cheap" in a "luxury" area, plan a primary search for that area, but add a strategic fallback to a nearby, more affordable area.
2. **Location Expert**: You know the UAE. If someone asks for "near Metro", you know to search Marina, JLT, or Business Bay.
3. **Property Categorization**: Strictly map requested types to (Apartment, Villa, Townhouse, Office, Penthouse).

### INTENT TYPES:
- `search`: Property discovery. Requires a `searchPlan`.
- `stats`: Market data analysis.
- `info`: Greetings, identity, or general UAE real estate questions not requiring a DB search.
- `clarification`: When the request is too vague (e.g., "I want a house" - needs city/budget).

### RESPONSE FORMAT (MUST BE JSON):
{
  "thought": "Your internal reasoning for this search strategy",
  "type": "search | stats | info | clarification",
  "searchPlan": {
    "primary": {
       "city": "Dubai|Abu Dhabi|Sharjah|Ajman",
       "area": "Specific area name",
       "beds": int, "minPrice": float, "maxPrice": float,
       "propertyType": "buy|rent",
       "category": "Apartment|Villa|Townhouse|Office|Penthouse",
       "isResidential": true
    },
    "fallback": {
       "area": "Alternative/nearby area",
       "reason": "Why this fallback?"
    }
  },
  "response": "Brief professional greeting or clarification message",
  "wantsTable": boolean
}
"""


def get_ai_intent(user_message, session_context=None):
    client = get_client()
    if not client:
        return {"type": "error", "response": "AI service currently unavailable (API key missing)."}

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        history = session_context.get('history', []) if session_context else []
        user_name = session_context.get('user_name')
        
        if not user_name:
            for msg in reversed(history):
                text = msg['content'].lower()
                if "my name is " in text:
                    user_name = msg['content'].split("is ")[-1].strip(' .!')
                    break
        
        if user_name:
            messages.append({"role": "system", "content": f"The user's name is {user_name}."})

        # Add context about what we currently see (filters, page)
        current_filters = session_context.get('filters', {})
        state_info = f"Current Session State: Filters={json.dumps(current_filters)}, Page={session_context.get('page', 1)}."
        messages.append({"role": "system", "content": state_info})

        trimmed_history = history[-6:]
        for msg in trimmed_history:
            messages.append({"role": msg['role'], "content": msg['content']})
            
        messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=400
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"AI intent extraction failed: {str(e)}")
        return {"type": "error", "response": f"AI Error: {str(e)}"}

def get_simple_response(user_message, context="greeting"):
    """Used for quick, non-streaming AI responses."""
    client = get_client()
    if not client:
        return "I am Houser AI, your UAE real estate advisor. How can I help you?"
        
    try:
        response = client.chat.completions.create(
            model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": "You are a brief, professional UAE real estate assistant. Provide a helpful 1-sentence response."},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "How can I assist you with your property needs today?"

def stream_professional_response(user_query, results, filters, is_fallback=False, is_supplemented=False, session_context=None):
    client = get_client()
    results_count = len(results)
    user_name = session_context.get('user_name', 'Client') if session_context else 'Client'
    
    if not client:
        yield f"{user_name}, I found {results_count} properties for you."
        return

    try:
        area = filters.get('area', 'Dubai')
        city = filters.get('city', 'Dubai')
        
        result_snippets = []
        for r in results[:5]:
            match_type = "EXACT MATCH" if r.get('isExactMatch') else "STRATEGIC RECOMMENDATION"
            result_snippets.append(f"[{match_type}] {r['title']} (AED {int(r['price']):,}, {r['beds']} Beds, {r['location']})")
        
        results_info = "; ".join(result_snippets)
        
        system_prompt = f"""You are Houser AI, an Elite UAE Real Estate Advisor.
        Analytically narrate these {results_count} results for {user_name}.
        
        DATA CONTEXT:
        - Query: {user_query}
        - Findings: {results_info}
        - Match Status: Fallback={is_fallback}, Supplemented={is_supplemented}
        
        ADVISORY RULES:
        1. Professional and data-centric. Address user as {user_name}.
        2. ANOMALY CHECK: If pricing/type in data seems off (e.g. 15,000 'sale'), note it professionally as a data anomaly.
        3. Never lie about locations.
        4. 2-3 sentences max.
        """
        
        response = client.chat.completions.create(
            model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Narrate the findings professionally."}
            ],
            temperature=0.7,
            max_tokens=300,
            stream=True
        )
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"{user_name}, I have curated {results_count} premium options in {area}."

def generate_stats_narrative(user_query, stats_data, session_context=None):
    client = get_client()
    user_name = session_context.get('user_name', 'Client') if session_context else 'Client'
    
    if not client or not stats_data:
        return f"{user_name}, I am analyzing the latest market data for you."

    try:
        area = stats_data.get('area', 'Dubai')
        avg = stats_data['prices']['avg']
        counts = stats_data['counts']['total']
        
        system_prompt = f"""You are a senior Market Analyst at Houser AI.
        Narrate statistics for {user_name} regarding {user_query}.
        
        DATA: Area={area}, AvgPrice={int(avg):,}, Listings={counts}.
        
        RULES:
        1. Professional and analytical.
        2. Explain the investment significance.
        3. 2-3 sentences max.
        """
        
        response = client.chat.completions.create(
            model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Narrate the stats."}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"The market in {area} shows an average entry of AED {int(avg):,}."

def generate_professional_response(user_query, results, filters, is_fallback=False, is_supplemented=False, session_context=None):
    gen = stream_professional_response(user_query, results, filters, is_fallback, is_supplemented, session_context)
    return "".join(list(gen))
