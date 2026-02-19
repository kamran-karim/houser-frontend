-- Minimal PostgreSQL schema for Houser seeds

CREATE SCHEMA IF NOT EXISTS public;

-- Countries
CREATE TABLE IF NOT EXISTS public.countries (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  code TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Cities
CREATE TABLE IF NOT EXISTS public.cities (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  country_id INTEGER REFERENCES public.countries(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Areas
CREATE TABLE IF NOT EXISTS public.areas (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  city_id INTEGER REFERENCES public.cities(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Categories
CREATE TABLE IF NOT EXISTS public.categories (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT DEFAULT 'active'
);

-- AI Prompts
CREATE TABLE IF NOT EXISTS public.ai_prompts (
  id SERIAL PRIMARY KEY,
  "key" TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Properties
CREATE TABLE IF NOT EXISTS public.properties (
  id SERIAL PRIMARY KEY,
  title TEXT,
  description TEXT,
  "location" TEXT,
  price NUMERIC(18,2) DEFAULT 0,
  bedrooms TEXT,
  bathrooms TEXT,
  amenities JSONB DEFAULT '{}'::jsonb,
  nearby JSONB DEFAULT '{}'::jsonb,
  "source" TEXT,
  thumbnail TEXT,
  property_type TEXT,
  status TEXT,
  built_status TEXT,
  country_id INTEGER REFERENCES public.countries(id) ON DELETE SET NULL,
  city_id INTEGER REFERENCES public.cities(id) ON DELETE SET NULL,
  area_id INTEGER REFERENCES public.areas(id) ON DELETE SET NULL,
  category_id INTEGER REFERENCES public.categories(id) ON DELETE SET NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  source_url TEXT,
  search_vector TSVECTOR
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_properties_status ON public.properties(status);
CREATE INDEX IF NOT EXISTS idx_properties_property_type ON public.properties(property_type);
CREATE INDEX IF NOT EXISTS idx_properties_price ON public.properties(price);
CREATE INDEX IF NOT EXISTS idx_properties_city_area ON public.properties(city_id, area_id);
CREATE INDEX IF NOT EXISTS idx_properties_search_vector ON public.properties USING GIN (search_vector);
